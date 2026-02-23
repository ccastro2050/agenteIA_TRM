# Documento 01 — Conceptos Fundamentales

**Proyecto:** agente_IA_TRM
**Serie:** Tutorial de construcción paso a paso
**Repositorio:** https://github.com/ccastro2050/agenteIA_TRM

---

## 1. Modelos de Lenguaje Grande (LLM)

Un **Modelo de Lenguaje Grande** (*Large Language Model*, LLM) es un sistema de inteligencia artificial entrenado sobre cantidades masivas de texto para aprender las estructuras estadísticas del lenguaje. A partir de ese entrenamiento, es capaz de generar texto coherente, responder preguntas, razonar sobre problemas y producir código.

Los LLMs más relevantes para este proyecto son:

| Proveedor | Modelo | Características |
|-----------|--------|-----------------|
| Anthropic | claude-sonnet-4-6 | Alto razonamiento, respuestas largas y detalladas |
| OpenAI | gpt-4o-mini | Rápido y económico, buena precisión |
| DeepSeek | deepseek-chat | Alternativa de bajo costo, API compatible con OpenAI |

> **Referencia:** Zhao, W. X. et al. (2023). *A Survey of Large Language Models*. arXiv:2303.18223.
> https://arxiv.org/abs/2303.18223

---

## 2. Agentes de IA

Un **agente de IA** es un sistema que, dado un objetivo expresado en lenguaje natural, decide de forma autónoma qué acciones tomar, las ejecuta, observa el resultado y repite el proceso hasta completar la tarea.

La diferencia fundamental con un LLM simple es:

```
LLM simple:   pregunta → respuesta   (una sola inferencia)
Agente de IA: objetivo → [planificar → actuar → observar → repetir] → resultado final
```

El agente tiene acceso a **herramientas** (*tools*): funciones externas que puede invocar para obtener datos reales, consultar bases de datos, hacer cálculos, etc.

> **Referencia:** Wang, L. et al. (2024). *A Survey on Large Language Model based Autonomous Agents*. Frontiers of Computer Science, 18(6).
> https://arxiv.org/abs/2308.11432

---

## 3. El Patrón ReAct

**ReAct** (*Reasoning + Acting*) es el patrón de razonamiento más extendido para construir agentes con LLMs. El modelo alterna entre dos tipos de pasos:

- **Thought (razonamiento):** el modelo razona sobre qué necesita para responder.
- **Action (acción):** invoca una herramienta específica.
- **Observation (observación):** recibe el resultado de la herramienta.
- Repite hasta tener suficiente información para dar la respuesta final.

Ejemplo real del proyecto:

```
Pregunta: ¿Cuál fue la TRM promedio del segundo semestre de 2024?

Thought: Necesito el histórico de TRM de los últimos 6 meses.
Action: analizar_historico_trm(meses=6)
Observation: {"trm_promedio": 4285.50, "tendencia": "alcista", ...}

Thought: Ya tengo los datos. Puedo responder.
Final Answer: La TRM promedio del segundo semestre de 2024 fue de $4.285,50...
```

> **Referencia:** Yao, S. et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR 2023.
> https://arxiv.org/abs/2210.03629

---

## 4. RAG — Generación Aumentada por Recuperación

**RAG** (*Retrieval-Augmented Generation*) es una técnica que combina dos componentes:

1. **Recuperación:** ante una pregunta, busca los fragmentos de texto más relevantes dentro de una base de documentos propia.
2. **Generación:** el LLM recibe esos fragmentos como contexto adicional y genera una respuesta basada en ellos.

El resultado es un agente que puede responder sobre documentos privados o actualizados sin necesidad de reentrenar el modelo.

```
Pregunta del usuario
       ↓
  Búsqueda semántica en documentos (pgvector)
       ↓
  Fragmentos relevantes recuperados
       ↓
  LLM genera respuesta usando esos fragmentos
       ↓
  Respuesta fundamentada en los documentos
```

En este proyecto, los documentos del DANE (desempleo, inflación, PIB, censo) se indexan en pgvector y el agente los consulta en cada pregunta relevante.

> **Referencia:** Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020.
> https://arxiv.org/abs/2005.11401

---

## 5. Embeddings y Vector Store — pgvector

### 5.1 Embeddings

Un **embedding** es una representación numérica de un texto como un vector de números reales. Textos con significados similares producen vectores cercanos en el espacio vectorial.

```
"tasa de desempleo"  →  [0.23, -0.81, 0.44, ..., 0.07]  (1536 dimensiones)
"mercado laboral"    →  [0.21, -0.79, 0.48, ..., 0.09]  ← vectores cercanos
"precio del café"    →  [-0.54, 0.12, -0.33, ..., 0.61] ← vector lejano
```

En este proyecto se usan los embeddings de OpenAI (`text-embedding-3-small`).

### 5.2 pgvector

Un **vector store** es una base de datos especializada en almacenar y buscar embeddings por similitud semántica. **pgvector** es una extensión de PostgreSQL que agrega este tipo de búsqueda a la base de datos relacional más popular del mundo.

Ventajas de pgvector:

- Persiste en disco (soluciones en memoria se pierden al reiniciar).
- Soporta filtros SQL junto con la búsqueda vectorial.
- Se administra igual que cualquier base de datos PostgreSQL.
- Escala con las herramientas estándar de PostgreSQL (backups, réplicas, etc.).

> **Referencia:** pgvector — Open-source vector similarity search for Postgres.
> https://github.com/pgvector/pgvector

---

## 6. LangChain

**LangChain** es el framework de Python más extendido para construir aplicaciones con LLMs. Proporciona abstracciones para:

- Conectarse a múltiples proveedores de LLMs con una interfaz unificada.
- Definir y gestionar herramientas (`@tool`).
- Construir cadenas de procesamiento (*chains*).
- Construir agentes ReAct con memoria y herramientas.

En este proyecto, LangChain se usa para el **agente simple** (`agente_langchain.py`): un único LLM con acceso a todas las herramientas disponibles.

> **Referencia:** LangChain Documentation. https://python.langchain.com/docs/introduction/
> **Referencia:** Chase, H. (2022). *LangChain*. GitHub. https://github.com/langchain-ai/langchain

---

## 7. LangGraph

**LangGraph** es una extensión de LangChain que permite construir agentes como **grafos de estado**. Cada nodo del grafo es una función; las aristas definen el flujo de ejecución, incluyendo ciclos y decisiones condicionales.

Esto habilita el patrón **multi-agente supervisor**:

```
Pregunta
    ↓
Supervisor (decide qué especialista necesita)
    ↓
┌───┴───────────┬──────────────┐
Agente TRM   Agente Datos   Agente RAG
    └───────────┴──────────────┘
                ↓
          Sintetizador
                ↓
           Respuesta final
```

En este proyecto, LangGraph maneja el **agente multi-agente** (`agente_langgraph.py`): el supervisor decide qué agente especializado debe atender cada consulta.

> **Referencia:** LangGraph Documentation. https://langchain-ai.github.io/langgraph/
> **Referencia:** LangGraph: Multi-Agent Workflows. https://blog.langchain.dev/langgraph-multi-agent-workflows/

---

## 8. FastAPI

**FastAPI** es el framework web de Python para construir APIs REST de alto rendimiento. Sus principales ventajas para este proyecto son:

- **Tipado estático con Pydantic:** valida automáticamente los datos de entrada y salida.
- **Documentación automática:** genera Swagger UI en `/docs` sin configuración adicional.
- **Asíncrono nativo:** soporta operaciones concurrentes con `async/await`.
- **Rendimiento:** comparable a Node.js y Go, muy superior a Flask para APIs.

En este proyecto, FastAPI expone los endpoints del agente (`/consulta`, `/metricas`, `/historial`) y sirve la interfaz web en `/ui`.

> **Referencia:** FastAPI Documentation. https://fastapi.tiangolo.com/
> **Referencia:** Ramírez, S. (2018). *FastAPI*. GitHub. https://github.com/tiangolo/fastapi

---

## 9. Arquitectura General del Proyecto

Todos los conceptos anteriores se integran en una sola plataforma:

```
┌─────────────────────────────────────────────────────────────┐
│                  INTERFAZ WEB (Bootstrap 5)                 │
│              http://localhost:8001/ui                       │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP POST /consulta
┌─────────────────────────▼───────────────────────────────────┐
│                    API REST (FastAPI)                        │
│              Pipeline → Middleware → SQLite                 │
└──────────┬──────────────────────────────┬───────────────────┘
           │                              │
┌──────────▼──────────┐     ┌─────────────▼──────────────────┐
│  Agente LangChain   │     │     Agente LangGraph            │
│  (ReAct · 1 LLM)    │     │  (Supervisor · 4 LLMs)          │
└──────────┬──────────┘     └─────────────┬──────────────────┘
           └──────────────────────────────┘
                          │ invocan tools
           ┌──────────────┼───────────────┐
     ┌─────▼─────┐  ┌─────▼──────┐  ┌────▼───────────┐
     │ Tools TRM │  │ Tools      │  │ Tools RAG       │
     │  (CSV)    │  │ Comercio   │  │ (pgvector)      │
     └───────────┘  └────────────┘  └────────────────┘
```

---

## 10. LangSmith — Trazabilidad y observabilidad

Cuando un agente de IA falla o da una respuesta inesperada, es difícil
saber exactamente qué ocurrió internamente: qué tool invocó, qué le
respondió, cómo razonó el LLM. **LangSmith** resuelve ese problema.

**LangSmith** es una plataforma de observabilidad para aplicaciones
construidas con LangChain y LangGraph. Registra cada paso de la
ejecución del agente y los muestra en una interfaz visual.

### ¿Qué registra LangSmith?

Para cada consulta que llega al agente, LangSmith guarda una **traza**
(*trace*) con todos los pasos internos:

```
Consulta: "¿Cuál fue la inflación en 2024?"
│
├── LLM Supervisor
│   ├── Input:  "Analiza la pregunta y elige el agente..."
│   └── Output: "Ruta: RAG"
│
├── Agente RAG
│   ├── Tool: buscar_documentos_dane("inflación 2024")
│   │   └── Resultado: 4 fragmentos del boletín IPC
│   └── LLM genera respuesta con esos fragmentos
│
└── Sintetizador
    ├── Input:  fragmentos + pregunta
    └── Output: "La inflación en 2024 fue del 5,17%..."

Métricas: 11.4 seg · 318 tokens · $0.000089 USD
```

### ¿Para qué sirve en la práctica?

| Situación | Sin LangSmith | Con LangSmith |
|-----------|--------------|---------------|
| El agente da una respuesta incorrecta | No se sabe por qué | Se ve exactamente qué tool invocó y qué datos usó |
| La respuesta tarda demasiado | No se sabe en qué paso | Se ve el tiempo de cada nodo del grafo |
| Se quiere mejorar un prompt | Hay que adivinar el efecto | Se comparan trazas antes y después del cambio |
| Se quiere auditar el uso | Solo hay logs de texto | Interfaz visual con filtros por fecha, modelo y proyecto |

### ¿Cómo se activa?

Se necesita una cuenta gratuita en https://smith.langchain.com y una
clave API. En este proyecto se configura desde la interfaz web
(sidebar → sección LangSmith) o directamente en el archivo `.env`.
Una vez configurada, todas las consultas quedan trazadas automáticamente.

> **Referencia:** LangSmith Documentation. https://docs.smith.langchain.com/
> **Referencia:** LangSmith — Observe and evaluate your LLM applications. https://smith.langchain.com/

---

## 11. API Keys — Claves de acceso a los servicios

Una **API key** (clave de API) es una cadena de texto que identifica y
autoriza a una aplicación para usar un servicio externo. Funciona como
una contraseña: sin ella, el servicio rechaza las peticiones.

En este proyecto se usan servicios de IA que cobran por uso. Cada
proveedor entrega una clave distinta.

### ¿Cuántas claves se necesitan?

**Con una sola clave de OpenAI es suficiente para arrancar el proyecto.**

Esto se debe a que los **embeddings** (la conversión de texto a vectores
para pgvector) se hacen exclusivamente con el modelo
`text-embedding-3-small` de OpenAI. No existe en este proyecto una
alternativa para esa función.

El LLM que responde las preguntas sí es intercambiable: puede ser
OpenAI, Anthropic o DeepSeek. Con la clave de OpenAI se cubren ambas
funciones a la vez.

| Clave | Para qué se usa | ¿Obligatoria? |
|-------|----------------|---------------|
| **OpenAI** | Embeddings (siempre) + LLM GPT (opcional) | **Sí** |
| **Anthropic** | LLM Claude (opcional) | No |
| **DeepSeek** | LLM DeepSeek (opcional) | No |

### Cómo obtener cada clave

**OpenAI** (obligatoria)
- Registro: https://platform.openai.com/signup
- Claves: https://platform.openai.com/api-keys
- Formato: `sk-proj-...`
- Costo: pago por uso · los embeddings cuestan ~$0.02 por millón de tokens

**Anthropic** (opcional)
- Registro: https://console.anthropic.com
- Claves: https://console.anthropic.com/settings/keys
- Formato: `sk-ant-api03-...`
- Costo: pago por uso · Claude Sonnet ~$3 / millón de tokens de entrada

**DeepSeek** (opcional)
- Registro: https://platform.deepseek.com
- Claves: https://platform.deepseek.com/api-keys
- Formato: `sk-...` (32 caracteres hexadecimales)
- Costo: pago por uso · deepseek-chat ~$0.14 / millón de tokens de entrada

### ¿Cómo se configuran en el proyecto?

Las claves se guardan en el archivo `.env` en la raíz del proyecto:

```
OPENAI_API_KEY=sk-proj-...        ← obligatoria
ANTHROPIC_API_KEY=sk-ant-...      ← solo si se usa Claude
DEEPSEEK_API_KEY=sk-...           ← solo si se usa DeepSeek
```

También se pueden cambiar en cualquier momento desde la interfaz web
(sidebar → campo API Key) sin necesidad de tocar el archivo `.env` ni
reiniciar el servidor.

> **Importante:** nunca compartir las API keys ni subirlas a un
> repositorio público. El archivo `.env` está incluido en `.gitignore`
> para evitar que se publiquen accidentalmente.

---

## 12. n8n — Automatización de flujos

**n8n** es una herramienta de automatización de flujos de trabajo (*workflow automation*).
Funciona de manera visual: el usuario conecta bloques (nodos) con flechas para definir
qué debe pasar cuando ocurre un evento.

```
[Evento disparador]  →  [Paso 1]  →  [Paso 2]  →  [Acción final]

Ejemplo:
[Nuevo correo recibido]  →  [Llamar al agente IA]  →  [Enviar respuesta por WhatsApp]
```

### ¿Qué tiene que ver n8n con este proyecto?

El agente de IA de este proyecto expone una API REST. Eso significa que cualquier
sistema externo puede invocarlo enviando una petición HTTP. n8n puede hacer eso
de forma visual, sin escribir código.

Casos de uso reales:

| Disparador en n8n | Acción | Resultado |
|---|---|---|
| Formulario web enviado | Llama a `/consulta` con la pregunta | El agente responde automáticamente |
| Correo electrónico recibido | Extrae la pregunta y llama a `/consulta` | La respuesta se reenvía por correo |
| Scheduler (cada hora) | Llama a `/metricas` | Envía reporte de uso a Slack |
| Webhook de WhatsApp | Llama a `/consulta` | El agente responde por WhatsApp |

### ¿Cómo se integra con este proyecto?

El proyecto genera automáticamente un archivo JSON (`agente_produccion_n8n.json`)
que describe el flujo para importar en n8n. El usuario lo descarga desde la
interfaz web (pestaña n8n), lo importa en su instancia de n8n y queda listo
para automatizar consultas al agente.

> **Referencia:** n8n Documentation. https://docs.n8n.io/
> **Referencia:** n8n — Source available workflow automation. https://github.com/n8n-io/n8n

---

## 13. Resumen de Tecnologías

| Componente | Tecnología | Versión mínima |
|---|---|---|
| Lenguaje | Python | 3.11 |
| Framework de agentes | LangChain | 1.2 |
| Grafos de agentes | LangGraph | 1.0 |
| API REST | FastAPI | 0.129 |
| Servidor ASGI | Uvicorn | 0.41 |
| Base de datos vectorial | pgvector (PostgreSQL 15+) | pg 15 |
| Embeddings | OpenAI text-embedding-3-small | — |
| Interfaz web | Bootstrap | 5.3 |
| Configuración dinámica | SQLite | Python stdlib |
| Validación de datos | Pydantic | 2.x |
| Automatización de flujos | n8n | 1.x |
| Trazabilidad / observabilidad | LangSmith | — |

---

## Referencias

1. Zhao, W. X. et al. (2023). *A Survey of Large Language Models*. arXiv:2303.18223. https://arxiv.org/abs/2303.18223

2. Wang, L. et al. (2024). *A Survey on Large Language Model based Autonomous Agents*. Frontiers of Computer Science, 18(6). https://arxiv.org/abs/2308.11432

3. Yao, S. et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR 2023. https://arxiv.org/abs/2210.03629

4. Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020. https://arxiv.org/abs/2005.11401

5. pgvector — Open-source vector similarity search for Postgres. https://github.com/pgvector/pgvector

6. LangChain Documentation. https://python.langchain.com/docs/introduction/

7. LangGraph Documentation. https://langchain-ai.github.io/langgraph/

8. FastAPI Documentation. https://fastapi.tiangolo.com/

9. Anthropic. (2024). *Claude Model Overview*. https://www.anthropic.com/claude

10. OpenAI. (2024). *GPT-4o System Card*. https://openai.com/index/gpt-4o-system-card/

11. DeepSeek AI. (2024). *DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model*. arXiv:2405.04434. https://arxiv.org/abs/2405.04434

12. Ramírez, S. (2018). *FastAPI*. GitHub. https://github.com/tiangolo/fastapi

13. LangSmith Documentation. https://docs.smith.langchain.com/

14. n8n Documentation. https://docs.n8n.io/

15. n8n — Source available workflow automation. GitHub. https://github.com/n8n-io/n8n

---

## Pasos Git

Ejecutar desde la carpeta raíz del proyecto `agenteIA_TRM/`:

```bash
git add tutorial_AgenteIA/01_conceptos_fundamentales.md
git commit -m "docs: agrega documento 01 - conceptos fundamentales"
git push -u origin main
```

> **Siguiente documento:** `02_arquitectura_sistema.md` — Diagrama de componentes y flujo completo de una consulta.
