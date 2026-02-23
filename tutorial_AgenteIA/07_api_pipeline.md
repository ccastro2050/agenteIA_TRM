# Documento 07 — API REST, Pipeline y Base de Datos

**Proyecto:** agente_IA_TRM
**Serie:** Tutorial de construcción paso a paso
**Prerequisito:** Documento 06 — Los Agentes
**Repositorio:** https://github.com/ccastro2050/agenteIA_TRM

---

## 1. Visión general de la capa de backend

Este documento cubre los cuatro archivos que conectan los agentes con el
mundo exterior:

| Archivo | Rol |
|---------|-----|
| `database.py` | SQLite — prompts, configuración, historial |
| `middleware.py` | Estimación de tokens, costos, logs JSONL |
| `pipeline.py` | Grafo LangGraph que orquesta agente + métricas + log |
| `main.py` | Servidor FastAPI — expone todo como API REST |

El flujo de una consulta es:

```
Cliente (UI / curl / n8n)
    ↓  POST /consulta
main.py
    ↓  pipeline.procesar_consulta()
pipeline.py (grafo de 3 nodos)
    ├─ nodo_ejecutar_agente   → agente_langchain / agente_langgraph
    ├─ nodo_calcular_metricas → middleware.estimar_tokens / calcular_costo
    └─ nodo_registrar         → middleware.registrar_consulta → SQLite + JSONL
    ↓
main.py retorna ConsultaResponse (JSON)
    ↓
Cliente recibe respuesta + latencia + tokens + costo
```

---

## 2. `database.py` — SQLite como base de datos operacional

### SQLite vs pgvector

El proyecto usa dos bases de datos con propósitos distintos:

| | SQLite | pgvector |
|---|---|---|
| **Tipo** | Relacional (tablas) | Vectorial (embeddings) |
| **Uso** | Configuración, prompts, historial | Búsqueda semántica en documentos |
| **Servidor** | No requiere servidor (archivo .db) | Requiere PostgreSQL corriendo |
| **Módulo Python** | `sqlite3` (incluido en Python) | `langchain-postgres` |
| **Archivo** | `agente_config.db` | Tablas en `bdvector` (PostgreSQL) |

SQLite es ideal para guardar configuración editable porque:
- Es un archivo local, sin servidor.
- `sqlite3` viene incluido en Python (sin instalación).
- Soporta transacciones ACID: las escrituras son seguras.

### Las 3 tablas de SQLite

```sql
-- Tabla 1: prompts de los agentes (editables desde la UI)
CREATE TABLE prompts (
    nombre     TEXT PRIMARY KEY,   -- ej: "langchain_main"
    contenido  TEXT NOT NULL,      -- el texto del prompt
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Tabla 2: configuración de la UI (proveedor, modelo, api_key)
CREATE TABLE configuracion (
    clave      TEXT PRIMARY KEY,   -- ej: "llm_provider"
    valor      TEXT NOT NULL,      -- ej: "openai"
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Tabla 3: historial de consultas con métricas
CREATE TABLE consultas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    pregunta    TEXT    NOT NULL,
    respuesta   TEXT    NOT NULL,
    latencia_ms REAL    DEFAULT 0,
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    costo_usd   REAL    DEFAULT 0,
    modelo      TEXT    DEFAULT '',
    backend     TEXT    DEFAULT 'langgraph'
);
```

### `INSERT OR IGNORE` e `INSERT OR REPLACE`

SQLite tiene dos variantes de `INSERT` muy útiles:

```sql
-- INSERT OR IGNORE: inserta solo si la clave NO existe
-- Se usa al inicializar los prompts por defecto: no sobreescribe ediciones del usuario
INSERT OR IGNORE INTO prompts (nombre, contenido)
VALUES ('langchain_main', '...');

-- INSERT OR REPLACE: inserta si no existe, reemplaza si ya existe (upsert)
-- Se usa al guardar cambios del usuario
INSERT OR REPLACE INTO prompts (nombre, contenido, updated_at)
VALUES ('langchain_main', 'nuevo texto', datetime('now'));
```

### `init_db()` — inicialización idempotente

```python
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)   # crea el archivo si no existe
    c    = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS prompts (...)")
    c.execute("CREATE TABLE IF NOT EXISTS configuracion (...)")
    c.execute("CREATE TABLE IF NOT EXISTS consultas (...)")

    for nombre, contenido in PROMPTS_DEFAULT.items():
        c.execute("INSERT OR IGNORE INTO prompts ...", (nombre, contenido))

    conn.commit()
    conn.close()
```

`init_db()` es **idempotente**: se puede llamar múltiples veces sin efecto
secundario. Si las tablas ya existen (`CREATE TABLE IF NOT EXISTS`),
no las toca. Si los prompts ya existen (`INSERT OR IGNORE`), no los sobreescribe.
Se llama automáticamente al arrancar el servidor (`@app.on_event("startup")`).

### Los 6 prompts por defecto

```python
PROMPTS_DEFAULT = {
    "langchain_main":         "...",   # prompt del agente ReAct
    "langgraph_supervisor":   "...",   # prompt del nodo supervisor
    "langgraph_trm":          "...",   # prompt del especialista TRM
    "langgraph_datos":        "...",   # prompt del especialista Datos
    "langgraph_rag":          "...",   # prompt del especialista RAG
    "langgraph_sintetizador": "...",   # prompt del sintetizador
}
```

Estos valores son los que aparecen en el Tab **Prompts** de la UI cuando
se abre por primera vez. El usuario puede editarlos y se guardan en SQLite.

---

## 3. `middleware.py` — Métricas, costos y logging

### Estimación de tokens

Los LLMs cobran por tokens, no por caracteres. Un token aproximado equivale
a 4 caracteres en español/inglés:

```python
def estimar_tokens(texto: str) -> int:
    return max(1, len(texto) // 4)
```

Esta es una estimación rápida, no exacta. Para conteos exactos se necesita
el tokenizador específico del modelo (ej: `tiktoken` para OpenAI). Para el
registro de costos, la estimación es suficientemente precisa.

### Cálculo de costo

```python
def calcular_costo(tokens_in: int, tokens_out: int) -> float:
    costos = config.COSTOS_POR_PROVEEDOR.get(config.LLM_PROVIDER,
                                              {"input": 0.001, "output": 0.003})
    return (tokens_in * costos["input"] + tokens_out * costos["output"]) / 1000
```

La tabla `COSTOS_POR_PROVEEDOR` en `config.py` tiene el precio por 1 000 tokens
para cada proveedor. Por ejemplo, para `gpt-4o-mini`:
- Input: $0.00015 / 1k tokens
- Output: $0.00060 / 1k tokens

### Formato JSONL

JSONL (JSON Lines) es un formato donde cada línea del archivo es un objeto
JSON completo. Es ideal para logs porque:
- Se puede escribir una línea a la vez (sin reescribir el archivo completo).
- Se puede leer línea por línea sin cargar todo en memoria.
- Cada línea es un JSON válido e independiente.

```python
# Escribir un registro
with open("logs/consultas.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(registro, ensure_ascii=False) + "\n")
```

```
# Ejemplo de archivo consultas.jsonl
{"timestamp": "2024-12-15T10:30:00", "pregunta": "¿Cuánto está el dólar?", "latencia_ms": 1250, ...}
{"timestamp": "2024-12-15T10:31:45", "pregunta": "¿Cuál fue la inflación?", "latencia_ms": 2100, ...}
```

### Doble persistencia: SQLite + JSONL

Cada consulta se guarda en dos lugares:

1. **SQLite** — fuente primaria, consultable con SQL, soporta métricas
   (percentiles, promedios, agrupaciones por modelo).

2. **JSONL** — backup legible, exportable, útil para análisis externo
   o si SQLite se corrompe.

```python
def registrar_consulta(...):
    # 1. SQLite — fuente primaria
    try:
        database.save_consulta(...)
    except Exception:
        pass  # no bloquea la respuesta si SQLite falla

    # 2. JSONL — backup
    with open(LOGS_FILE, "a") as f:
        f.write(json.dumps(registro) + "\n")
```

El `try / except` alrededor de SQLite garantiza que incluso si la base de
datos falla (permisos, disco lleno), el JSONL sigue recibiendo el log.

### Métricas y percentiles

```python
def get_metricas_consultas() -> dict:
    c.execute("SELECT latencia_ms FROM consultas ORDER BY latencia_ms")
    lats = [r[0] for r in c.fetchall()]   # lista ordenada

    def pct(lst, p):
        return round(lst[max(0, int(len(lst) * p / 100) - 1)], 1)

    return {
        "latencia_p50_ms": pct(lats, 50),   # mediana
        "latencia_p95_ms": pct(lats, 95),   # 95% de requests terminan antes de esto
        "latencia_p99_ms": pct(lats, 99),   # 99%
        ...
    }
```

**P95** significa que el 95% de las consultas tardaron menos que ese valor.
Si el P95 es 5 segundos, el 5% restante tardó más de 5 segundos. Es la
métrica más usada en sistemas de producción para medir la "cola" de latencia.

---

## 4. `pipeline.py` — El meta-grafo de producción

### Por qué un pipeline separado de los agentes

Los agentes (`agente_langchain.py`, `agente_langgraph.py`) solo saben
responder preguntas. El pipeline añade tres responsabilidades que no
son del agente:

1. **Medir el tiempo** que tarda la respuesta.
2. **Estimar tokens y costo** de esa respuesta.
3. **Registrar** todo en SQLite y JSONL.

Usar un grafo LangGraph para el pipeline (en vez de una función lineal)
permite modificar fácilmente el orden de los pasos o agregar nuevos nodos
sin tocar el código del agente.

### Los 3 nodos del pipeline

```
START → nodo_ejecutar_agente → nodo_calcular_metricas → nodo_registrar → END
```

#### `nodo_ejecutar_agente`

```python
def nodo_ejecutar_agente(estado: EstadoConsulta) -> dict:
    inicio  = time.time()
    backend = estado.get("backend", "langgraph")

    if backend == "langchain":
        import agente_langchain
        respuesta = agente_langchain.ejecutar_agente(
            pregunta=estado["pregunta"], silencioso=True,
            system_prompt=estado.get("prompts", {}).get("langchain_main"),
        )
    else:
        import agente_langgraph
        respuesta = agente_langgraph.ejecutar_agente(
            pregunta=estado["pregunta"], silencioso=True,
            prompts={...},  # prompts del request
        )

    latencia_ms = (time.time() - inicio) * 1000
    return {"respuesta": respuesta, "latencia_ms": latencia_ms, ...}
```

Los imports (`import agente_langchain`) son **dentro** de la función para
evitar importar ambos agentes al mismo tiempo (lazy loading).

#### `nodo_calcular_metricas`

```python
def nodo_calcular_metricas(estado: EstadoConsulta) -> dict:
    tokens_in  = middleware.estimar_tokens(estado["pregunta"])
    tokens_out = middleware.estimar_tokens(estado["respuesta"])
    costo_usd  = middleware.calcular_costo(tokens_in, tokens_out)
    return {"tokens_in": tokens_in, "tokens_out": tokens_out, "costo_usd": costo_usd}
```

#### `nodo_registrar`

```python
def nodo_registrar(estado: EstadoConsulta) -> dict:
    middleware.registrar_consulta(
        pregunta=estado["pregunta"],
        respuesta=estado["respuesta"],
        latencia_ms=estado["latencia_ms"],
        ...
    )
    return {}   # no modifica el estado
```

### `procesar_consulta()` — la función que llama `main.py`

```python
def procesar_consulta(pregunta: str, backend: str = "langgraph",
                      temperatura: float = 0.2,
                      prompts: dict | None = None) -> dict:
    app = obtener_pipeline()   # lazy loading del grafo

    estado_inicial = {
        "pregunta":    pregunta,
        "backend":     backend,
        "temperatura": temperatura,
        "prompts":     prompts or {},
        "respuesta":   "", "latencia_ms": 0.0,
        "tokens_in":   0,  "tokens_out":  0,
        "costo_usd":   0.0, "timestamp":  "",
    }

    estado_final = app.invoke(estado_inicial)

    return {
        "respuesta":    estado_final["respuesta"],
        "latencia_ms":  estado_final["latencia_ms"],
        "tokens_total": estado_final["tokens_in"] + estado_final["tokens_out"],
        "costo_usd":    estado_final["costo_usd"],
        "modelo":       _modelo_activo(),   # lee SQLite dinámicamente
        "backend":      backend,
    }
```

---

## 5. `main.py` — El servidor FastAPI

### FastAPI en 3 conceptos

**FastAPI** es un framework web moderno para construir APIs REST en Python:

1. **Async**: las rutas se definen con `async def`, lo que permite manejar
   múltiples requests simultáneos sin bloquear el servidor.

2. **Pydantic**: los modelos de request y response se validan automáticamente.
   Si el cliente envía un campo con tipo incorrecto, FastAPI retorna un 422
   con el mensaje de error exacto.

3. **OpenAPI automático**: FastAPI genera la documentación Swagger en `/docs`
   leyendo el código, sin escribirla a mano.

### Pydantic — validación automática

```python
from pydantic import BaseModel, Field

class ConsultaRequest(BaseModel):
    pregunta:    str   = Field(..., min_length=5, max_length=2000)
    temperatura: float = Field(default=0.2, ge=0.0, le=1.0)
    backend:     str   = Field(default="langgraph")
    prompts:     dict  = Field(default=None)
```

Si el cliente envía `temperatura: 5.0`, FastAPI retorna automáticamente:
```json
{"detail": [{"msg": "ensure this value is less than or equal to 1.0", ...}]}
```

`...` como valor por defecto en `Field` significa que el campo es
**obligatorio** (sin valor por defecto).

### `@app.on_event("startup")`

```python
@app.on_event("startup")
async def startup_event():
    database.init_db()
```

Este decorador registra una función que se ejecuta **una vez** cuando el
servidor arranca, antes de aceptar cualquier request. Aquí se inicializa
SQLite para garantizar que las tablas existen desde el primer request.

### CORS — Cross-Origin Resource Sharing

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # permite llamadas desde cualquier origen
    allow_methods=["*"],
    allow_headers=["*"],
)
```

CORS es un mecanismo de seguridad del navegador: por defecto, una página
web en `http://localhost:3000` no puede hacer fetch a `http://localhost:8001`
porque son orígenes distintos. Al configurar CORS con `allow_origins=["*"]`,
se permite que cualquier origen llame a la API, incluyendo n8n y la UI Bootstrap.

### Los endpoints principales

```
POST /consulta
  ← ConsultaRequest {pregunta, temperatura, backend, prompts}
  → ConsultaResponse {respuesta, latencia_ms, tokens_in/out, costo, modelo, ...}

GET /health
  → HealthResponse {status: "ok", modelo, vector_store, langsmith, timestamp}

GET /metricas
  → dict {total_consultas, latencia_p50/p95/p99, tokens_total, costo_total, ...}

GET /historial?n=50
  → list[dict] con las últimas 50 consultas

GET /api/config
  → dict {llm_provider, llm_model, vector_store, langsmith_enabled, ...}

POST /api/config
  ← dict {llm_provider: "deepseek", llm_model: "deepseek-chat", llm_api_key: "..."}
  → {ok: true, guardadas: ["llm_provider", "llm_model", "llm_api_key"]}

GET  /api/prompts
  → dict {langchain_main: "...", langgraph_supervisor: "...", ...}

PUT  /api/prompts/{nombre}
  ← {contenido: "nuevo texto del prompt"}
  → {ok: true, nombre: "langchain_main"}
```

### LangSmith — activación dinámica

```python
@app.post("/consulta")
async def consultar(req: ConsultaRequest):
    db_cfg  = database.get_all_config()
    ls_key  = db_cfg.get("langsmith_api_key", "") or config.LANGSMITH_API_KEY
    ls_proj = db_cfg.get("langsmith_project",  "") or config.LANGSMITH_PROJECT

    if ls_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"]     = ls_key
        os.environ["LANGCHAIN_PROJECT"]     = ls_proj
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
    ...
```

LangSmith se activa en cada request si hay una clave disponible (SQLite o .env).
Esto permite habilitar/deshabilitar el tracing desde la UI sin reiniciar el servidor.

### Manejo de errores

```python
try:
    resultado = pipeline.procesar_consulta(...)
except Exception as e:
    tipo = type(e).__name__
    raise HTTPException(status_code=500, detail=f"[{tipo}] {e}")
```

Si el agente lanza una excepción (clave API inválida, PostgreSQL caído, etc.),
FastAPI retorna un JSON con el código de error:
```json
{"detail": "[AuthenticationError] Incorrect API key provided"}
```

La UI captura el código 500 y muestra el mensaje al usuario en rojo
sin que la página quede bloqueada.

---

## 6. Probar el backend desde la terminal

```bash
# Verificar SQLite
python database.py
# → SQLite: .../agente_config.db
# → Prompts: ['langchain_main', 'langgraph_supervisor', ...]

# Probar el pipeline directamente
python pipeline.py --pregunta "¿Cuánto está el dólar?"
python pipeline.py --backend langchain --pregunta "¿Qué exporta Colombia?"

# Iniciar el servidor
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Probar el endpoint desde otra terminal
curl -X POST http://localhost:8001/consulta \
     -H "Content-Type: application/json" \
     -d '{"pregunta": "¿Cuánto está el dólar?", "backend": "langchain"}'

# Ver métricas
curl http://localhost:8001/metricas

# Ver historial
curl http://localhost:8001/historial?n=5
```

---

## Referencias

1. FastAPI — Documentación oficial.
   https://fastapi.tiangolo.com/

2. Pydantic — Validación de datos con Python.
   https://docs.pydantic.dev/

3. Python sqlite3 — Módulo incluido en Python.
   https://docs.python.org/3/library/sqlite3.html

4. JSONL — JSON Lines format.
   https://jsonlines.org/

5. CORS en FastAPI.
   https://fastapi.tiangolo.com/tutorial/cors/

6. LangSmith — Observabilidad para agentes LangChain.
   https://docs.smith.langchain.com/

---

## Pasos Git

```bash
git add database.py middleware.py pipeline.py main.py tutorial_AgenteIA/07_api_pipeline.md
git commit -m "feat: agrega backend completo (database, middleware, pipeline, main) y documento 07"
git push origin main
```

> **Siguiente documento:** `08_interfaz_web.md` — La interfaz Bootstrap 5
> (`templates/index.html`): estructura HTML, JavaScript con fetch API,
> tabs de Chat/Prompts/Métricas/Historial, y cómo integrar con n8n.
