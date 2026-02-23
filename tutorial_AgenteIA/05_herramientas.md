# Documento 05 — Las Herramientas del Agente

**Proyecto:** agente_IA_TRM
**Serie:** Tutorial de construcción paso a paso
**Prerequisito:** Documento 04 — Preparación de Datos
**Repositorio:** https://github.com/ccastro2050/agenteIA_TRM

---

## 1. ¿Qué es una herramienta en LangChain?

En el contexto de los agentes de IA, una **herramienta** (tool) es una
función Python que el LLM puede llamar para obtener información o ejecutar
acciones que están fuera de su conocimiento interno.

El LLM por sí solo:
- Tiene conocimiento general hasta su fecha de corte.
- No puede leer archivos CSV locales.
- No puede consultar una base de datos vectorial.
- No conoce el precio del dólar de hoy.

Con herramientas, el agente puede:
- Leer `trm_2024.csv` y devolver la TRM actual.
- Buscar en pgvector los fragmentos más relevantes sobre inflación.
- Calcular estadísticas sobre exportaciones en tiempo real.

---

## 2. El decorador `@tool`

LangChain necesita que cada herramienta esté registrada de una manera
específica para que el LLM sepa cuándo y cómo usarla. Esto se hace con
el decorador `@tool`:

```python
from langchain_core.tools import tool

@tool
def obtener_trm_actual() -> str:
    """
    Retorna la tasa de cambio representativa del mercado (TRM)
    más reciente del año 2024, junto con la variación respecto
    al mes anterior.
    No requiere parámetros.
    """
    # ... código de la función
```

El decorador `@tool` hace tres cosas:
1. **Envuelve** la función en un objeto `StructuredTool` que LangChain entiende.
2. **Extrae el nombre** de la herramienta (el nombre de la función).
3. **Usa el docstring** como descripción que el LLM lee para decidir cuándo llamarla.

### La docstring es la instrucción del LLM

Este es un concepto fundamental: **el LLM nunca ve el código de la función**.
Solo ve su nombre y su docstring. Por eso el docstring debe ser claro y
específico sobre qué hace la herramienta, qué parámetros acepta y cuándo usarla.

```
Docstring clara:
    "Retorna la TRM más reciente. No requiere parámetros."
    → El LLM entiende: cuando me pregunten por el dólar, llamo esto.

Docstring pobre:
    "Función para TRM."
    → El LLM no sabe cuándo ni cómo usarla.
```

---

## 3. Por qué las herramientas retornan JSON

Todas las herramientas de este proyecto retornan un **string JSON**, no un
diccionario Python:

```python
import json

return json.dumps({
    "mes":  "Diciembre",
    "trm":  4359.0,
    "nota": "Fuente: Banco de la República",
}, ensure_ascii=False, indent=2)
```

Esto es intencional: el LLM recibe texto, no objetos Python. Al retornar
JSON como string, el LLM puede leer los datos estructurados y usarlos
para construir su respuesta.

`ensure_ascii=False` permite que los caracteres con tilde y la ñ se lean
correctamente en lugar de convertirse a secuencias de escape (`\u00e9`).

---

## 4. Las 6 herramientas del proyecto

Las herramientas se organizan en tres grupos según el tipo de datos que consultan:

```
tools.py
├── TOOLS_TRM   → CSV trm_2024.csv
│   ├── obtener_trm_actual()
│   └── analizar_historico_trm(meses)
│
├── TOOLS_DATOS → CSV comercio exterior
│   ├── consultar_balanza_comercial()
│   └── analizar_sectores_exportacion()
│
└── TOOLS_RAG   → pgvector (documentos DANE)
    ├── buscar_documentos_dane(query, k)
    └── listar_reportes_dane()
```

Al final del archivo se exportan las listas:

```python
TOOLS_TRM   = [obtener_trm_actual, analizar_historico_trm]
TOOLS_DATOS = [consultar_balanza_comercial, analizar_sectores_exportacion]
TOOLS_RAG   = [buscar_documentos_dane, listar_reportes_dane]
TOOLS_TODOS = TOOLS_TRM + TOOLS_DATOS + TOOLS_RAG
```

Estas listas se importan en `agente_langchain.py` y `agente_langgraph.py`
para asignarle herramientas a cada agente.

---

## 5. Grupo 1 — Herramientas TRM

### `obtener_trm_actual()`

Lee `datos/trm_2024.csv`, toma la última fila (mes más reciente) y la
penúltima (mes anterior), y construye una interpretación en lenguaje natural:

```python
@tool
def obtener_trm_actual() -> str:
    import pandas as pd
    df  = pd.read_csv(config.DATOS_DIR / "trm_2024.csv")
    ult = df.iloc[-1]   # última fila → mes más reciente
    ant = df.iloc[-2]   # penúltima   → mes anterior

    direccion = "subió" if float(ult["variacion_pct"]) > 0 else "bajó"
    interpretacion = (
        f"El dólar {direccion} {abs(float(ult['variacion_pct'])):.2f}% "
        f"en {ult['nombre_mes']} respecto a {ant['nombre_mes']}."
    )
    return json.dumps({
        "mes":   ult["nombre_mes"],
        "trm":   float(ult["trm"]),
        "interpretacion": interpretacion,
    }, ensure_ascii=False, indent=2)
```

**Cuándo la usa el agente:** preguntas como "¿cuánto está el dólar?",
"¿cuál fue la TRM en diciembre?", "¿subió o bajó el dólar?".

**Salida de ejemplo:**
```json
{
  "mes": "Diciembre",
  "año": 2024,
  "trm": 4359.0,
  "variacion_pct": 2.45,
  "trm_mes_anterior": 4252.0,
  "interpretacion": "El dólar subió 2.45% en Diciembre respecto a Noviembre."
}
```

---

### `analizar_historico_trm(meses)`

Toma los últimos N meses del CSV y calcula estadísticas del período:

```python
@tool
def analizar_historico_trm(meses: int = 6) -> str:
    df  = pd.read_csv(...).tail(meses)   # últimos N meses
    variacion = (trm_fin - trm_inicio) / trm_inicio * 100
    tendencia = "alcista" if variacion > 0 else "bajista"
    ...
```

**Cuándo la usa el agente:** "¿cuál fue la tendencia del dólar en el
último trimestre?", "compara el TRM del primer y segundo semestre".

---

## 6. Grupo 2 — Herramientas Datos

### `consultar_balanza_comercial()`

Lee `comercio_exterior_2024.csv` y calcula los totales anuales:

```python
@tool
def consultar_balanza_comercial() -> str:
    df          = pd.read_csv(config.DATOS_DIR / "comercio_exterior_2024.csv")
    total_exp   = df["exportaciones_usd_mill"].sum()
    total_imp   = df["importaciones_usd_mill"].sum()
    balanza_tot = total_exp - total_imp
    tipo        = "superávit" if balanza_tot >= 0 else "déficit"
    ...
```

**Cuándo la usa el agente:** "¿Colombia tiene déficit comercial?",
"¿en qué mes fueron mayores las exportaciones?".

---

### `analizar_sectores_exportacion()`

Lee `exportaciones_sectores_2024.csv`, ordena por participación y calcula
el top 3 y los sectores con mayor crecimiento:

```python
@tool
def analizar_sectores_exportacion() -> str:
    df   = pd.read_csv(...).sort_values("participacion_pct", ascending=False)
    top3 = df.head(3)[["sector", "participacion_pct"]].to_dict("records")
    ...
```

**Cuándo la usa el agente:** "¿cuál es el principal producto de exportación
de Colombia?", "¿qué sectores crecieron más en exportaciones?".

---

## 7. Grupo 3 — Herramientas RAG

Estas herramientas son las únicas que interactúan con pgvector.

### Lazy loading — inicialización diferida

Cargar el vector store (conectarse a PostgreSQL) tiene un costo en tiempo.
Si se hiciera al importar el módulo, el servidor tardaría más en iniciar
incluso cuando no se necesita RAG. La solución es el **lazy loading**:

```python
_vectorstore_rag = None   # variable global, inicia vacía

def _obtener_vectorstore():
    global _vectorstore_rag
    if _vectorstore_rag is None:           # solo la primera vez
        embeddings = crear_embeddings(config)
        _vectorstore_rag = cargar_vectorstore(embeddings, config)
    return _vectorstore_rag   # las veces siguientes: retorna el ya cargado
```

La primera vez que el agente llama a `buscar_documentos_dane()`, se carga
el vector store y queda guardado en `_vectorstore_rag`. Las llamadas
siguientes reusan el mismo objeto sin reconectarse.

---

### `buscar_documentos_dane(query, k)`

Convierte la `query` del usuario en un vector (con el mismo modelo de
embeddings que se usó al indexar) y busca los `k` fragmentos más cercanos
en pgvector:

```python
@tool
def buscar_documentos_dane(query: str, k: int = 4) -> str:
    vs         = _obtener_vectorstore()
    resultados = vs.similarity_search_with_score(query, k=k)

    fragmentos = []
    for doc, distancia in resultados:
        # Convertir distancia coseno a relevancia 0-1
        relevancia = round(max(0.0, 1.0 - distancia / 2.0), 3)
        fragmentos.append({
            "texto":      doc.page_content,
            "fuente":     doc.metadata["fuente"],
            "relevancia": relevancia,
        })
    return json.dumps({"fragmentos": fragmentos}, ensure_ascii=False, indent=2)
```

**`similarity_search_with_score()`** retorna una lista de tuplas
`(Document, distancia)`. La distancia es un número: menor distancia
significa mayor similitud. Se transforma en un valor de relevancia
entre 0 y 1 para que sea más intuitivo en la respuesta del agente.

**Cuándo la usa el agente:** cualquier pregunta sobre desempleo, inflación,
PIB o demografía que requiera información de los reportes DANE.

**Salida de ejemplo:**
```json
{
  "query": "tasa de desempleo Colombia",
  "k": 4,
  "fragmentos": [
    {
      "texto": "La tasa global de participación fue de 62.7%...",
      "fuente": "boletin_desempleo_2024",
      "titulo": "Boletin Desempleo 2024",
      "relevancia": 0.921
    },
    ...
  ],
  "total": 4
}
```

---

### `listar_reportes_dane()`

Retorna el catálogo de documentos disponibles en el índice. No consulta
pgvector: el catálogo está hardcodeado en el código porque los documentos
no cambian. Es útil cuando el usuario pregunta "¿qué información tiene
el agente?" o antes de hacer una búsqueda.

```python
@tool
def listar_reportes_dane() -> str:
    catalogo = [
        {"nombre": "boletin_desempleo_2024", "tema": "Desempleo y mercado laboral", ...},
        {"nombre": "boletin_ipc_2024",       "tema": "Inflación y precios",         ...},
        ...
    ]
    return json.dumps({"documentos_disponibles": catalogo}, ensure_ascii=False, indent=2)
```

---

## 8. Manejo de errores en las herramientas

Todas las herramientas tienen un bloque `try / except` que atrapa cualquier
error y lo retorna como JSON en lugar de lanzar una excepción:

```python
try:
    # ... lógica normal
    return json.dumps({...})

except Exception as e:
    return json.dumps({"error": f"Descripción del error: {str(e)}"},
                      ensure_ascii=False)
```

Si el LLM recibe un JSON con la clave `"error"`, puede comunicarle al
usuario que hubo un problema en lugar de fallar silenciosamente.

---

## 9. Flujo completo cuando el agente usa una herramienta

```
Usuario: "¿Cuánto está el dólar?"
         │
         ▼
LLM lee el mensaje + lista de herramientas disponibles
         │
         ▼
LLM decide: "Debo llamar obtener_trm_actual()"
         │
         ▼
Agente ejecuta: obtener_trm_actual()
  └─ Lee trm_2024.csv
  └─ Calcula variación
  └─ Retorna JSON con TRM y análisis
         │
         ▼
LLM recibe el JSON como contexto adicional
         │
         ▼
LLM genera respuesta final en lenguaje natural:
"El dólar se encuentra a $4,359 pesos colombianos (diciembre 2024),
 lo que representa un incremento del 2.45% respecto a noviembre."
```

Este ciclo (Razonar → Actuar → Observar → Razonar) es el patrón
**ReAct** explicado en el Documento 01.

---

## 10. Verificar que las herramientas funcionan

Con el entorno virtual activo, probar las herramientas directamente
en Python sin necesidad de iniciar el servidor:

```bash
python -c "
from tools import obtener_trm_actual, listar_reportes_dane
print(obtener_trm_actual.invoke({}))
print(listar_reportes_dane.invoke({}))
"
```

Para probar la búsqueda semántica (requiere haber ejecutado `preparar_base.py`):

```bash
python -c "
from tools import buscar_documentos_dane
resultado = buscar_documentos_dane.invoke({'query': 'desempleo Colombia', 'k': 2})
print(resultado)
"
```

Nota: con el decorador `@tool`, las herramientas se llaman con `.invoke()`
en lugar de llamarlas directamente como funciones.

---

## Referencias

1. LangChain — Defining Custom Tools.
   https://python.langchain.com/docs/how_to/custom_tools/

2. LangChain — `@tool` decorator.
   https://python.langchain.com/docs/concepts/tools/

3. LangChain — `similarity_search_with_score`.
   https://python.langchain.com/docs/integrations/vectorstores/pgvector/

4. Python — `json.dumps` con `ensure_ascii=False`.
   https://docs.python.org/3/library/json.html

5. Pandas — `read_csv`, `iloc`, `tail`.
   https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html

---

## Pasos Git

```bash
git add tools.py tutorial_AgenteIA/05_herramientas.md
git commit -m "feat: agrega tools.py y documento 05 - herramientas del agente"
git push origin main
```

> **Siguiente documento:** `06_agentes.md` — Construcción del agente ReAct
> con LangChain (`agente_langchain.py`) y del sistema multi-agente supervisor
> con LangGraph (`agente_langgraph.py`).
