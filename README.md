# agenteIA_TRM — Agente IA de Analítica Económica Colombiana
**Agentes IA para la Analítica de Datos · USB Medellín**

---

## Objetivo

Agente de analítica económica colombiana listo para producción:
- **FastAPI**: API REST con documentación OpenAPI automática
- **Bootstrap 5**: interfaz web interactiva (chat, prompts, métricas, historial)
- **LangGraph**: pipeline de producción con trazabilidad
- **pgvector**: búsqueda semántica sobre reportes del DANE (PostgreSQL)
- **Middleware**: métricas de latencia, tokens y costo por request
- **LangSmith**: trazabilidad end-to-end en producción

> **Proyecto 100% autónomo** — no depende de ningún otro capítulo.
> Incluye su propio agente, datos, vector store y API.

---

## Arquitectura

```
Bootstrap 5 UI (http://localhost:8001/ui)
    │  fetch API
    ▼
FastAPI main.py (puerto 8001)
    │  invoca
    ▼
pipeline.py  ─── LangGraph (3 nodos)
    │
    ├─ nodo_ejecutar_agente   → agente_langchain.py / agente_langgraph.py → tools.py → LLM
    ├─ nodo_calcular_metricas → middleware.py (tokens, costo)
    └─ nodo_registrar         → logs/consultas.jsonl
```

### Pipeline LangGraph (3 nodos)

| Nodo | Responsabilidad |
|------|----------------|
| `ejecutar_agente` | Invoca el agente ReAct con las 6 herramientas |
| `calcular_metricas` | Estima tokens y calcula costo USD |
| `registrar` | Persiste el log en `logs/consultas.jsonl` |

### Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/ui` | Interfaz web Bootstrap 5 |
| `POST` | `/consulta` | Envía una pregunta al agente |
| `GET` | `/health` | Estado del servicio |
| `GET` | `/metricas` | Latencia p50/p95/p99, costos, tokens |
| `GET` | `/historial` | Últimas N consultas |
| `GET` | `/version` | Versión y configuración |
| `GET` | `/api/prompts` | Prompts activos (SQLite) |
| `PUT` | `/api/prompts/{nombre}` | Editar un prompt |
| `GET` | `/api/config` | Configuración activa |
| `POST` | `/api/config` | Actualizar configuración |
| `GET` | `/api/modelos` | Modelos disponibles por proveedor |
| `GET` | `/api/archivos` | Listar datos y documentos |
| `POST` | `/api/upload/{carpeta}` | Subir archivo |
| `DELETE` | `/api/archivos/{carpeta}/{nombre}` | Eliminar archivo |
| `GET` | `/api/n8n-workflow` | Workflow n8n en JSON |
| `GET` | `/docs` | Documentación Swagger UI |
| `GET` | `/redoc` | Documentación ReDoc |

---

## Estructura de archivos

```
agenteIA_TRM/
├── main.py               ← FastAPI: endpoints REST + UI Bootstrap
├── pipeline.py           ← LangGraph: pipeline de producción (3 nodos)
├── agente_langchain.py   ← Agente ReAct LangChain (TRM + comercio + DANE)
├── agente_langgraph.py   ← Agente supervisor multi-nodo LangGraph
├── tools.py              ← 6 herramientas especializadas
├── middleware.py         ← Costos, latencia, logging JSONL
├── database.py           ← SQLite: prompts y configuración UI
├── preparar_base.py      ← Ingesta DANE → pgvector
├── vectorstore_factory.py ← Backend pgvector
├── exportar_dashboard.py ← 4 CSVs con métricas operativas
├── langgraph_to_n8n.py   ← Exporta pipeline a JSON n8n
├── config.py             ← Configuración centralizada
├── templates/
│   └── index.html        ← SPA Bootstrap 5 (6 tabs)
├── datos/
│   ├── trm_2024.csv
│   ├── comercio_exterior_2024.csv
│   └── exportaciones_sectores_2024.csv
├── documentos/
│   ├── boletin_desempleo_2024.txt
│   ├── boletin_ipc_2024.txt
│   ├── cuentas_nacionales_pib_2024.txt
│   └── censo_poblacion_2023.txt
├── logs/                 ← consultas.jsonl (generado al usar la API)
├── resultados/           ← CSVs del dashboard (generados por exportar_dashboard.py)
├── .env                  ← Claves de ejemplo — reemplaza con las tuyas
├── .env.example          ← Plantilla de referencia
└── requirements.txt
```

---

## Instalación y ejecución

```bash
cd agenteIA_TRM
pip install -r requirements.txt
```

### Paso 1 — Configurar claves de API

Edita `.env` y reemplaza los valores `XXXXXXX` con tus claves reales.
**Nunca hagas `git add .env` con claves reales.**

```bash
# Opción segura: variables de entorno del sistema operativo
# Windows PowerShell:
$env:OPENAI_API_KEY = "sk-..."

# Linux / macOS:
export OPENAI_API_KEY="sk-..."
```

### Paso 2 — Iniciar PostgreSQL con pgvector

```bash
# Con Docker (recomendado):
docker run -d --name pgvector \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=bdvector \
  -p 5432:5432 pgvector/pgvector:pg16
```

### Paso 3 — Preparar el índice vectorial

```bash
python preparar_base.py
```

### Paso 4 — Iniciar la API REST

```bash
# Desarrollo (con recarga automática):
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Producción:
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2
```

La API queda disponible en:
- **Interfaz web**: http://localhost:8001/ui
- **Documentación**: http://localhost:8001/docs
- **Health check**: http://localhost:8001/health

### Paso 5 — Hacer una consulta de prueba

```bash
# Con Python (LangChain):
python agente_langchain.py --pregunta "¿Cuánto está el dólar hoy en Colombia?"

# Con Python (LangGraph):
python agente_langgraph.py --pregunta "¿Cuál fue la inflación en 2024?"
```

```powershell
# Con PowerShell (Windows):
Invoke-RestMethod -Method Post -Uri http://localhost:8001/consulta `
  -ContentType "application/json" `
  -Body '{"pregunta": "cuanto esta el dolar?"}'
```

```bash
# Con curl (Linux / macOS / Git Bash):
curl -X POST http://localhost:8001/consulta \
     -H "Content-Type: application/json" \
     -d '{"pregunta": "cuanto esta el dolar?"}'
```

O directamente desde el navegador: **http://localhost:8001/ui** → tab Chat.

### Paso 6 — Ver métricas operativas

```bash
# Desde la API:
curl http://localhost:8001/metricas

# Exportar CSVs:
python exportar_dashboard.py
```

### Paso 7 — Generar n8n JSON y PNG

```bash
python langgraph_to_n8n.py
python langgraph_to_n8n.py --grafo    # también genera grafo_produccion.png
```

---

## Cambiar proveedor LLM

Edita `.env`:

```bash
# Anthropic (Claude Sonnet)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6

# OpenAI (GPT-4o-mini — más barato)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# DeepSeek (muy económico)
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

# Local con Ollama (sin costo)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
```

También puedes cambiar el modelo desde la interfaz web en **http://localhost:8001/ui** → panel lateral → Guardar configuración.

---

## Tabla de costos estimados

| Proveedor | Input (1K tokens) | Output (1K tokens) | 100 consultas/día |
|-----------|-------------------|--------------------|--------------------|
| Claude Sonnet | $0.003 | $0.015 | ~$0.50 |
| GPT-4o-mini | $0.00015 | $0.0006 | ~$0.03 |
| DeepSeek | $0.00014 | $0.00028 | ~$0.02 |
| Ollama (local) | $0.00 | $0.00 | $0.00 |

---

## LangSmith — Trazabilidad en producción

Las trazas de cada request se envían automáticamente si `LANGSMITH_API_KEY` está configurada.

Ver trazas en: https://smith.langchain.com
Proyecto: `agenteIA-TRM`

---

## Importar en n8n

1. Ejecutar: `python langgraph_to_n8n.py`
2. Abrir n8n → menú `⋮` (tres puntos) → **Import from file**
3. Seleccionar `langgraph_to_n8n.json`
4. El nodo `ejecutar_agente` ya apunta a `http://localhost:8001/consulta`
5. Ajustar credenciales si la API está en otra URL

---

## Herramientas del agente

| Grupo | Herramienta | Descripción |
|-------|-------------|-------------|
| TRM | `obtener_trm_actual` | TRM diciembre 2024 + variación |
| TRM | `analizar_historico_trm(meses)` | Tendencia últimos N meses |
| Comercio | `consultar_balanza_comercial` | Exportaciones vs importaciones 2024 |
| Comercio | `analizar_sectores_exportacion` | Sectores y participación |
| RAG | `listar_reportes_dane` | Catálogo de documentos DANE |
| RAG | `buscar_documentos_dane(query)` | Búsqueda semántica en reportes DANE |

---

*agenteIA_TRM · Agentes IA para la Analítica de Datos · USB Medellín*
