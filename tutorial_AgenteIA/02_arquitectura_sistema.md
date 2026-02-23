# Documento 02 — Arquitectura del Sistema

**Proyecto:** agente_IA_TRM
**Serie:** Tutorial de construcción paso a paso
**Prerequisito:** Documento 01 — Conceptos Fundamentales
**Repositorio:** https://github.com/ccastro2050/agenteIA_TRM

---

## 1. ¿Qué hace este sistema?

El sistema es un **asistente de IA** que responde preguntas sobre
economía colombiana en lenguaje natural. El usuario escribe una pregunta
en español, y el sistema:

1. La recibe por una interfaz web o por API.
2. La envía a un agente de IA.
3. El agente decide qué herramientas necesita para responder.
4. Las herramientas consultan archivos CSV o documentos indexados en
   una base de datos vectorial (pgvector).
5. El agente genera una respuesta en lenguaje natural.
6. La respuesta vuelve al usuario junto con métricas de uso
   (tiempo, costo estimado, tokens consumidos).

**Ejemplo:**

```
Usuario:  "¿Cuál fue la tasa de desempleo en Colombia en el tercer
           trimestre de 2024?"

Sistema:  "Según el boletín técnico del DANE, la tasa de desempleo
           en Colombia en el tercer trimestre de 2024 fue del 10,8%,
           lo que representa una reducción de 0,4 puntos porcentuales
           respecto al mismo período de 2023..."
```

---

## 2. Los cinco bloques del sistema

El sistema se divide en cinco bloques. Cada bloque tiene una
responsabilidad clara y bien definida. Esta separación facilita
entender, modificar y escalar el sistema.

```
┌──────────────────────────────────────────────────────────────┐
│  BLOQUE 1 — Interfaz Web                                     │
│  El usuario escribe su pregunta aquí                         │
│  Tecnología: HTML + Bootstrap 5 + JavaScript                 │
└───────────────────────────┬──────────────────────────────────┘
                            │ envía la pregunta por HTTP (JSON)
┌───────────────────────────▼──────────────────────────────────┐
│  BLOQUE 2 — API REST                                         │
│  Recibe la pregunta, coordina todo el proceso y              │
│  devuelve la respuesta al navegador                          │
│  Tecnología: FastAPI (Python)                                │
└─────────┬────────────────────────────────┬───────────────────┘
          │ elige uno de los dos agentes    │ guarda métricas
          │                                │
┌─────────▼──────────────────┐  ┌──────────▼──────────────────┐
│  BLOQUE 3 — Agentes de IA  │  │  BLOQUE 4 — Base de datos   │
│                            │  │  operacional                │
│  Opción A: LangChain       │  │                             │
│  (un LLM · todas las tools)│  │  SQLite                     │
│                            │  │  · historial de consultas   │
│  Opción B: LangGraph       │  │  · configuración activa     │
│  (supervisor + 3 agentes   │  │  · prompts editables        │
│   especializados)          │  │                             │
└─────────┬──────────────────┘  └─────────────────────────────┘
          │ invoca herramientas (tools)
┌─────────▼────────────────────────────────────────────────────┐
│  BLOQUE 5 — Herramientas y datos                             │
│                                                              │
│  Tools TRM      → lee datos/trm_2024.csv                    │
│  Tools Comercio → lee datos/comercio_exterior_2024.csv       │
│  Tools RAG      → busca en documentos indexados en pgvector  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Bloque 1 — Interfaz Web

La interfaz web es una página HTML que el usuario abre en su navegador
en la dirección `http://localhost:8001/ui`.

Está construida con **Bootstrap 5** (librería de estilos y componentes
visuales) y **JavaScript** puro. No requiere React ni ningún framework
adicional de frontend.

### ¿Qué puede hacer el usuario desde la interfaz?

| Pestaña | Función |
|---------|---------|
| **Chat** | Escribir la pregunta, elegir el agente y ver la respuesta |
| **Prompts** | Editar el texto de instrucciones de cada agente |
| **Métricas** | Ver estadísticas: latencia, tokens, costo acumulado |
| **Historial** | Consultar las últimas N peticiones realizadas |
| **Archivos** | Subir archivos CSV y PDF al sistema |
| **n8n** | Descargar el workflow JSON para importar en n8n |

### ¿Cómo se comunica con el servidor?

La interfaz usa la función `fetch()` de JavaScript para enviar
peticiones HTTP al servidor y recibir las respuestas en formato JSON.
Todo ocurre sin recargar la página.

```
[Usuario hace clic en "Consultar"]
         ↓
JavaScript recopila la pregunta, el agente elegido y los prompts
         ↓
fetch('POST /consulta', { pregunta, backend, temperatura, prompts })
         ↓
Espera la respuesta del servidor
         ↓
Muestra la respuesta en pantalla
```

---

## 4. Bloque 2 — API REST (FastAPI)

La API REST es el **coordinador central** del sistema. Corre en el
servidor y escucha peticiones HTTP en el puerto 8001.

### 4.1 Endpoints principales

Un **endpoint** es una URL a la que se puede enviar una petición.
Cada endpoint realiza una función específica:

| Método | URL | Función |
|--------|-----|---------|
| `GET` | `/ui` | Sirve la interfaz web al navegador |
| `POST` | `/consulta` | Recibe la pregunta y devuelve la respuesta del agente |
| `GET` | `/metricas` | Devuelve estadísticas de uso |
| `GET` | `/historial` | Devuelve las últimas N consultas |
| `GET` | `/api/config` | Lee la configuración activa |
| `POST` | `/api/config` | Guarda nueva configuración (modelo, API key, etc.) |
| `GET` | `/api/prompts` | Lee los prompts actuales |
| `PUT` | `/api/prompts/{nombre}` | Actualiza un prompt |
| `GET` | `/docs` | Documentación automática Swagger |

### 4.2 Flujo interno de `/consulta`

Cuando llega una petición a `/consulta`, la API ejecuta este flujo:

```
1. Recibe la pregunta en formato JSON
         ↓
2. Valida los datos con Pydantic
   (tipo de dato correcto, campos obligatorios presentes)
         ↓
3. Lee la configuración activa desde SQLite
   (proveedor LLM, modelo, API key, vector store)
         ↓
4. Activa LangSmith si hay clave configurada
   (permite ver las trazas de ejecución del agente)
         ↓
5. Llama al agente elegido (LangChain o LangGraph)
         ↓
6. Recibe la respuesta del agente
         ↓
7. Calcula métricas: latencia en ms, tokens, costo estimado en USD
         ↓
8. Guarda el registro en SQLite y en logs/consultas.jsonl
         ↓
9. Devuelve la respuesta + métricas al cliente en JSON
```

---

## 5. Bloque 3 — Los dos agentes

El sistema ofrece **dos agentes** que comparten las mismas herramientas.
El usuario elige cuál usar en la interfaz.

### 5.1 Agente LangChain — simple y directo

Un único LLM con acceso a todas las herramientas. Usa el patrón ReAct
(explicado en el Documento 01) para decidir qué herramientas invocar.

```
Pregunta del usuario
         ↓
    LLM (un solo modelo)
         ↓
    ¿Qué tool necesito?
         ↓
    Invoca la tool
         ↓
    ¿Tengo suficiente información?
    ├── No → invoca otra tool
    └── Sí → genera la respuesta final
```

**Cuándo usarlo:** preguntas sobre un solo tema (solo TRM, o solo
desempleo, o solo comercio exterior).

### 5.2 Agente LangGraph — supervisor y especialistas

Varios LLMs trabajando en equipo. Un supervisor decide qué especialista
atiende cada parte de la consulta.

```
Pregunta del usuario
         ↓
  LLM Supervisor
  "¿Qué especialista(s) necesito?"
         ↓
  ┌──────┴──────────┬────────────────┐
  ▼                 ▼                ▼
Agente TRM     Agente Datos     Agente RAG
(tipo cambio)  (comercio ext.)  (documentos DANE)
  └──────┬──────────┴────────────────┘
         ▼
  LLM Sintetizador
  "Combino los resultados en una sola respuesta"
         ↓
  Respuesta final al usuario
```

**Cuándo usarlo:** preguntas que combinan varios temas. Ejemplo:
*"¿Cómo afectó la devaluación del peso a las exportaciones en 2024?"*
(requiere datos de TRM y de comercio exterior al mismo tiempo).

### 5.3 Comparativa

| Criterio | LangChain | LangGraph |
|----------|-----------|-----------|
| Velocidad | Más rápido | Más lento (más llamadas al LLM) |
| Costo | Menor | Mayor |
| Preguntas simples | Excelente | Funciona, pero excesivo |
| Preguntas complejas | Puede quedarse corto | Excelente |
| Número de LLMs | 1 | 4 (supervisor + 3 agentes + sintetizador) |

---

## 6. Bloque 4 — Base de datos operacional (SQLite)

**SQLite** es una base de datos relacional que vive en un único archivo
(`agente_config.db`) dentro del proyecto. No requiere instalar un
servidor de base de datos: Python la lee y escribe directamente.

El sistema usa SQLite para tres propósitos:

### Tabla `configuracion`

Guarda la configuración activa. Cuando el usuario cambia el modelo en
la interfaz web, se actualiza esta tabla y el siguiente request ya
usa el nuevo modelo, **sin necesidad de reiniciar el servidor**.

| Clave | Ejemplo de valor |
|-------|-----------------|
| `llm_provider` | `deepseek` |
| `llm_model` | `deepseek-chat` |
| `llm_api_key` | `sk-xxxx...` |
| `vector_store` | `pgvector` |

### Tabla `prompts`

Guarda el texto de instrucciones de cada agente. El usuario puede
editarlos desde la pestaña "Prompts" de la interfaz, sin tocar el código.

| Nombre | Descripción |
|--------|-------------|
| `langchain_main` | Instrucciones del agente LangChain |
| `langgraph_supervisor` | Instrucciones del supervisor |
| `langgraph_trm` | Instrucciones del agente de TRM |
| `langgraph_datos` | Instrucciones del agente de comercio exterior |
| `langgraph_rag` | Instrucciones del agente de documentos DANE |
| `langgraph_sintetizador` | Instrucciones del sintetizador |

### Tabla `consultas`

Guarda el historial completo de todas las consultas realizadas.

| Campo | Descripción |
|-------|-------------|
| `timestamp` | Fecha y hora de la consulta |
| `pregunta` | Texto de la pregunta |
| `respuesta` | Texto de la respuesta |
| `latencia_ms` | Tiempo de respuesta en milisegundos |
| `tokens_in` | Tokens enviados al LLM |
| `tokens_out` | Tokens generados por el LLM |
| `costo_usd` | Costo estimado en dólares |
| `modelo` | Proveedor y modelo usados |
| `backend` | `langchain` o `langgraph` |

### ¿Por qué SQLite y no pgvector para estos datos?

pgvector es una base de datos **vectorial**: está optimizada para
búsqueda semántica por similitud entre vectores. No es adecuada para
guardar configuraciones o historial con estructura relacional.

SQLite es una base de datos **relacional**: está optimizada para
consultas estructuradas (filtrar por fecha, ordenar por costo, contar
consultas por modelo, etc.).

Cada tecnología se usa para lo que mejor sabe hacer.

---

## 7. Bloque 5 — Herramientas (Tools) y datos

Las herramientas son funciones de Python que el agente puede invocar.
Se definen con el decorador `@tool` de LangChain, que las registra y
las hace disponibles para el agente.

### Grupo 1 — Tools de TRM

Leen el archivo `datos/trm_2024.csv`.

| Tool | ¿Qué devuelve? |
|------|----------------|
| `obtener_trm_actual` | TRM más reciente de 2024 y variación respecto al mes anterior |
| `analizar_historico_trm` | Mínimo, máximo, promedio, tendencia de los últimos N meses |

### Grupo 2 — Tools de comercio exterior

Leen los archivos `datos/comercio_exterior_2024.csv` y
`datos/exportaciones_sectores_2024.csv`.

| Tool | ¿Qué devuelve? |
|------|----------------|
| `consultar_balanza_comercial` | Exportaciones, importaciones y saldo mensual de 2024 |
| `analizar_sectores_exportacion` | Participación % por sector: petróleo, café, flores, etc. |

### Grupo 3 — Tools RAG

Buscan en los documentos PDF indexados en pgvector.

| Tool | ¿Qué devuelve? |
|------|----------------|
| `buscar_documentos_dane` | Los K fragmentos más relevantes para la consulta |
| `listar_reportes_dane` | Lista de documentos disponibles en el índice |

Los documentos disponibles en el índice son:

| Documento | Tema | Período |
|-----------|------|---------|
| `boletin_desempleo_2024` | Mercado laboral | Q3 2024 |
| `boletin_ipc_2024` | Inflación / IPC | Diciembre 2024 |
| `cuentas_nacionales_pib_2024` | PIB y crecimiento | Año 2024 |
| `censo_poblacion_2023` | Demografía | 2023 |

---

## 8. pgvector — cómo funciona la búsqueda semántica

### Paso 1 — Indexación (se hace una sola vez)

Este proceso lo ejecuta el script `preparar_base.py` antes de arrancar
el servidor por primera vez.

```
Archivo PDF o TXT
         ↓
Dividir en fragmentos de ~800 caracteres
(cada fragmento es un "chunk")
         ↓
Para cada fragmento:
  Llamar a OpenAI text-embedding-3-small
  Recibir un vector de 1536 números
         ↓
Guardar en pgvector:
  texto del fragmento + vector + metadatos (fuente, título)
```

### Paso 2 — Consulta (cada vez que el agente busca)

```
Pregunta: "¿Cuál fue la inflación en 2024?"
         ↓
Calcular el embedding de la pregunta
(también un vector de 1536 números)
         ↓
pgvector busca los K fragmentos cuyo vector
sea más cercano al vector de la pregunta
         ↓
Devuelve los K fragmentos más relevantes
         ↓
El LLM los usa como contexto para generar la respuesta
```

La "cercanía" entre vectores se mide con **similitud coseno**: dos
vectores son cercanos si apuntan en la misma dirección, sin importar
su magnitud. Textos con significado similar producen vectores que
apuntan en la misma dirección.

---

## 9. Flujo completo de una consulta real

Para unificar todo lo anterior, se sigue paso a paso una consulta real:

```
[1] Usuario escribe en la interfaz:
    "¿Cuánto fue la inflación en Colombia en 2024?"
    Elige: agente LangGraph · temperatura 0.2

[2] JavaScript envía al servidor:
    POST /consulta
    { "pregunta": "...", "backend": "langgraph", "temperatura": 0.2 }

[3] FastAPI recibe la petición:
    · Valida el JSON
    · Lee de SQLite: modelo=deepseek-chat, store=pgvector
    · Llama al pipeline

[4] Pipeline LangGraph:
    · LLM Supervisor recibe la pregunta
    · Decide: "inflación → Agente RAG"
    · Agente RAG llama a buscar_documentos_dane("inflación 2024")

[5] Tool RAG:
    · Calcula embedding de "inflación 2024"
    · pgvector devuelve 4 fragmentos del boletín IPC
    · Fragmentos incluyen: "El IPC de 2024 fue 5,17%..."

[6] Sintetizador:
    · Recibe los fragmentos
    · Genera respuesta en lenguaje natural

[7] FastAPI devuelve:
    {
      "respuesta":  "La inflación en Colombia en 2024 fue del 5,17%...",
      "latencia_ms": 11420,
      "tokens_total": 318,
      "costo_estimado_usd": 0.000089,
      "modelo": "deepseek/deepseek-chat",
      "backend": "langgraph"
    }

[8] La interfaz muestra:
    · Respuesta renderizada en formato Markdown
    · Badges: 11420 ms · 318 tokens · $0.0001 USD · langgraph
    · Registro guardado automáticamente en historial
```

---

## 10. Estructura de archivos del proyecto

```
agenteIA_TRM/
│
├── .env                       ← claves API y configuración inicial
├── requirements.txt           ← dependencias Python
├── preparar_base.py           ← indexa documentos en pgvector (una vez)
│
├── config.py                  ← carga configuración (.env + SQLite)
├── database.py                ← acceso a SQLite
├── tools.py                   ← las 6 herramientas del agente
├── agente_langchain.py        ← agente simple (ReAct)
├── agente_langgraph.py        ← agente multi-agente (supervisor)
├── pipeline.py                ← orquesta el agente y mide métricas
├── middleware.py              ← calcula tokens, costos, escribe logs
├── main.py                    ← servidor FastAPI (todos los endpoints)
│
├── datos/                     ← archivos CSV con datos tabulares
│   ├── trm_2024.csv
│   ├── comercio_exterior_2024.csv
│   └── exportaciones_sectores_2024.csv
│
├── documentos/                ← PDFs y TXTs para indexar en pgvector
│   ├── boletin_desempleo_2024.txt
│   ├── boletin_ipc_2024.txt
│   ├── cuentas_nacionales_pib_2024.txt
│   └── censo_poblacion_2023.txt
│
├── templates/
│   └── index.html             ← interfaz web Bootstrap 5
│
├── logs/
│   └── consultas.jsonl        ← backup de consultas en texto plano
│
└── tutorial_AgenteIA/         ← esta serie de documentos
```

Cada archivo tiene **una sola responsabilidad**. Esta separación se
llama principio de responsabilidad única y hace que el código sea más
fácil de entender, probar y modificar.

---

## 11. ¿Por qué estas tecnologías?

| Decisión | Alternativa descartada | Razón de la elección |
|----------|----------------------|----------------------|
| FastAPI | Flask, Django | Más rápido, tipado automático, Swagger incluido sin configuración |
| LangGraph | Solo LangChain | Permite flujos multi-agente con control preciso del flujo |
| pgvector | FAISS, Chroma | Persiste en disco, se administra con herramientas PostgreSQL estándar |
| SQLite | JSON plano, YAML | Permite consultas SQL, más robusto para historial y configuración |
| Bootstrap 5 | React, Vue, Angular | Sin compilación ni dependencias de build, funciona con HTML puro |
| n8n | Zapier, Make | Código abierto, se puede instalar localmente sin costo por ejecución |

---

## Referencias

1. FastAPI Documentation. https://fastapi.tiangolo.com/

2. LangChain — Conceptual Guide.
   https://python.langchain.com/docs/concepts/

3. LangGraph — How it works.
   https://langchain-ai.github.io/langgraph/concepts/

4. pgvector — Open-source vector similarity search for Postgres.
   https://github.com/pgvector/pgvector

5. SQLite — When to use SQLite.
   https://www.sqlite.org/whentouse.html

6. Bootstrap 5 Documentation.
   https://getbootstrap.com/docs/5.3/

7. n8n Documentation. https://docs.n8n.io/

8. Johnson, J. et al. (2019). *Billion-scale similarity search with GPUs*.
   IEEE Transactions on Big Data. https://arxiv.org/abs/1702.08734

---

## Pasos Git

```bash
git add tutorial_AgenteIA/02_arquitectura_sistema.md
git commit -m "docs: agrega documento 02 - arquitectura del sistema"
git push origin main
```

> **Siguiente documento:** `03_configuracion_entorno.md` — Python,
> entorno virtual, instalación de dependencias, variables de entorno
> y estructura de carpetas paso a paso.
