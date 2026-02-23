# Documento 06 — Los Agentes

**Proyecto:** agente_IA_TRM
**Serie:** Tutorial de construcción paso a paso
**Prerequisito:** Documento 05 — Las Herramientas
**Repositorio:** https://github.com/ccastro2050/agenteIA_TRM

---

## 1. Dos implementaciones del agente

El proyecto tiene dos agentes que responden las mismas preguntas pero con
enfoques distintos:

| | `agente_langchain.py` | `agente_langgraph.py` |
|---|---|---|
| **Patrón** | ReAct simple | Multi-agente supervisor |
| **Decisión** | El LLM elige libremente qué herramientas usar | El grafo programa el ruteo entre especialistas |
| **LLMs activos** | 1 (el agente ReAct) | 4 (supervisor + 3 especialistas + sintetizador) |
| **Herramientas** | Las 6 disponibles al mismo tiempo | Cada especialista ve solo las suyas |
| **Mejor para** | Preguntas simples o cruzadas simples | Preguntas que requieren especialización clara |
| **Backend en UI** | `langchain` | `langgraph` |

Ambos agentes exponen la misma función `ejecutar_agente(pregunta)` y son
llamados desde `pipeline.py` según el campo `backend` de la petición.

---

## 2. `agente_langchain.py` — Agente ReAct con LangChain

### El system prompt

El **system prompt** (prompt del sistema) es el texto que se le entrega
al LLM al inicio de cada conversación para decirle quién es y qué puede
hacer. No lo ve el usuario, pero es la instrucción más importante:

```python
SYSTEM_PROMPT = """Eres un analista económico de Colombia con acceso
a tres dominios de información:

1. TIPO DE CAMBIO (TRM)
   - obtener_trm_actual()
   - analizar_historico_trm(meses)

2. COMERCIO EXTERIOR
   - consultar_balanza_comercial()
   - analizar_sectores_exportacion()

3. DOCUMENTOS DANE
   - listar_reportes_dane()
   - buscar_documentos_dane(query, k)

INSTRUCCIONES:
- Cita siempre los números exactos de las herramientas (no inventes cifras).
- Responde SIEMPRE en español con una conclusión clara al final.
..."""
```

El system prompt cumple varias funciones:
- Le dice al LLM **qué herramientas tiene** y para qué sirve cada una.
- Le da **instrucciones de comportamiento**: citar fuentes, responder en español.
- Define el **tono**: analista económico formal.

En la interfaz web, los prompts se pueden editar desde el tab **Prompts**
sin necesidad de modificar el código.

### `create_react_agent` — el corazón del agente

`create_react_agent` de LangGraph es la función que ensambla el agente
ReAct. Recibe el LLM y la lista de herramientas y construye internamente
un grafo de conversación:

```python
from langgraph.prebuilt import create_react_agent

agente = create_react_agent(
    model=llm,              # el LLM que razona y toma decisiones
    tools=TOOLS_TODOS,      # lista de 6 herramientas disponibles
    state_modifier=system_prompt,  # instrucciones del sistema
)

resultado = agente.invoke({"messages": [("user", pregunta)]})
respuesta = resultado["messages"][-1].content
```

El agente funciona en un ciclo hasta que decide que tiene suficiente
información para responder:

```
1. LLM recibe la pregunta + system prompt + lista de herramientas
2. LLM razona: "¿qué herramienta necesito?"
3. Si necesita herramienta → llama a la herramienta → recibe el JSON
4. LLM razona sobre el resultado → ¿necesito más información?
5. Si sí → vuelve al paso 2 con la herramienta necesaria
6. Si no → genera la respuesta final en lenguaje natural
```

### Prioridad de prompts

La función `ejecutar_agente` tiene una lógica de tres niveles para
determinar qué prompt usar:

```python
def ejecutar_agente(pregunta: str, system_prompt: str | None = None) -> str:
    # 1. Si viene un prompt como parámetro, usarlo (llamada desde la API con prompts editados)
    if system_prompt is None:
        try:
            # 2. Si no, buscar en SQLite (prompts guardados en la UI)
            import database
            system_prompt = database.get_prompt("langchain_main") or SYSTEM_PROMPT
        except Exception:
            # 3. Si SQLite falla, usar la constante del módulo
            system_prompt = SYSTEM_PROMPT
    ...
```

Esta jerarquía permite que el agente sea completamente configurable desde
la UI sin tocar el código, pero también tenga un comportamiento sensato
por defecto si se llama directamente desde la terminal.

### Probar el agente desde la terminal

```bash
# Pregunta por defecto
python agente_langchain.py

# Pregunta específica
python agente_langchain.py --pregunta "¿Cuánto está el dólar en diciembre 2024?"

# Pregunta cruzada (usa varias herramientas)
python agente_langchain.py --pregunta "¿Cómo se compara la inflación con la devaluación del peso?"
```

---

## 3. `agente_langgraph.py` — Sistema Multi-Agente Supervisor

### Por qué un sistema multi-agente

Un solo agente ReAct con 6 herramientas puede:
- Confundirse sobre qué herramienta priorizar en preguntas complejas.
- Mezclar dominios cuando debería ser preciso en cada uno.

El patrón multi-agente resuelve esto con **especialización**:
- El **supervisor** solo decide a quién derivar (no responde).
- Cada **especialista** ve solo sus herramientas (no se distrae).
- El **sintetizador** integra todo al final.

### El estado compartido — `EstadoMultiagente`

El estado es el mecanismo mediante el cual los nodos del grafo se comunican.
Se define como un `TypedDict` de Python:

```python
from typing import TypedDict

class EstadoMultiagente(TypedDict):
    pregunta:        str   # la pregunta del usuario (no cambia)
    ruta:            str   # "trm" | "datos" | "rag" | "multiple" (lo escribe el supervisor)
    justificacion:   str   # explicación del supervisor sobre la ruta elegida
    resp_trm:        str   # respuesta del agente TRM (vacío si no fue consultado)
    resp_datos:      str   # respuesta del agente Datos
    resp_rag:        str   # respuesta del agente RAG
    respuesta_final: str   # respuesta del sintetizador
    prompts:         dict  # prompts personalizados (opcional)
```

**TypedDict** es una clase de Python que define el "tipo" de un diccionario:
los nombres y tipos de sus claves. LangGraph usa esto para validar que los
nodos escriben y leen los campos correctos.

Cada nodo recibe el estado completo y retorna **solo el campo que modifica**:

```python
def nodo_supervisor(estado: EstadoMultiagente) -> dict:
    # ... lógica ...
    return {"ruta": "trm", "justificacion": "Pregunta sobre tipo de cambio"}
    # LangGraph hace el merge: el resto del estado no cambia
```

### Los 5 nodos del grafo

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  supervisor  │────▶│  agente_trm │────▶│  sintetizar │
└─────────────┘     └─────────────┘  ┌─▶└─────────────┘
       │                 │ (multiple) │
       │            ┌────┘            │
       │            ▼                 │
       │       ┌─────────────┐        │
       │       │  agente_rag │────────┘
       │       └─────────────┘
       │
       │       ┌─────────────┐     ┌─────────────┐
       └──────▶│ agente_datos│────▶│  sintetizar │
               └─────────────┘     └─────────────┘
```

#### Nodo supervisor — el enrutador

Pide al LLM que clasifique la pregunta en una de 4 rutas y que responda
**exactamente** en formato JSON:

```python
PROMPT_SUPERVISOR = (
    "Clasifica la pregunta en UNA de estas rutas:\n"
    "  'trm'      → tipo de cambio, dólar, TRM\n"
    "  'datos'    → exportaciones, importaciones, balanza comercial\n"
    "  'rag'      → desempleo, inflación, PIB, población\n"
    "  'multiple' → combina varios dominios\n\n"
    "Responde EXACTAMENTE con este JSON:\n"
    '{\"ruta\": \"<ruta>\", \"justificacion\": \"<una oración>\"}'
)
```

El nodo parsea el JSON y escribe `ruta` en el estado. Si el LLM responde
con markdown (```json...```), el código lo limpia antes de parsear.
Si hay error de parseo, cae a la ruta `"rag"` como comportamiento seguro.

#### Nodos especialistas — agente_trm, agente_datos, agente_rag

Cada especialista tiene su propio LLM con su propio system prompt y
solo ve las herramientas de su dominio:

```python
def nodo_agente_trm(estado: EstadoMultiagente) -> dict:
    llm = config.crear_llm_dinamico(temperature=0.1)
    system_trm = estado.get("prompts", {}).get("trm") or PROMPT_TRM

    sub_agente = create_react_agent(
        model=llm,
        tools=agent_tools.TOOLS_TRM,   # ← solo 2 herramientas
        state_modifier=system_trm,
    )
    resultado = sub_agente.invoke({"messages": [("user", estado["pregunta"])]})
    return {"resp_trm": resultado["messages"][-1].content}
```

El agente TRM no sabe que existen las herramientas de comercio exterior
o de RAG. Esa separación es intencional y mejora la precisión.

#### Nodo sintetizador

Recibe las respuestas de todos los especialistas que participaron y
las integra en una respuesta coherente:

```python
def nodo_sintetizar(estado: EstadoMultiagente) -> dict:
    partes = []
    if estado.get("resp_trm"):
        partes.append(f"=== AGENTE TRM ===\n{estado['resp_trm']}")
    if estado.get("resp_rag"):
        partes.append(f"=== AGENTE RAG ===\n{estado['resp_rag']}")

    contexto = "\n\n".join(partes)
    # El sintetizador recibe el contexto y genera la respuesta final
    respuesta = llm.invoke([SystemMessage(...), HumanMessage(contexto)])
    return {"respuesta_final": respuesta.content}
```

### Armar el grafo — `construir_grafo()`

```python
from langgraph.graph import StateGraph, START, END

grafo = StateGraph(EstadoMultiagente)   # ← tipo del estado

# Registrar nodos
grafo.add_node("supervisor",   nodo_supervisor)
grafo.add_node("agente_trm",   nodo_agente_trm)
grafo.add_node("agente_datos", nodo_agente_datos)
grafo.add_node("agente_rag",   nodo_agente_rag)
grafo.add_node("sintetizar",   nodo_sintetizar)

# Edge fija: el grafo siempre empieza en supervisor
grafo.add_edge(START, "supervisor")

# Edge condicional: supervisor → especialista según ruta
grafo.add_conditional_edges(
    "supervisor",
    enrutar_desde_supervisor,      # función que devuelve el nombre del siguiente nodo
    {
        "agente_trm":   "agente_trm",
        "agente_datos": "agente_datos",
        "agente_rag":   "agente_rag",
    },
)

# Edge condicional: agente_trm → agente_rag (si es "multiple") o → sintetizar
grafo.add_conditional_edges(
    "agente_trm",
    enrutar_desde_trm,
    {"agente_rag": "agente_rag", "sintetizar": "sintetizar"},
)

# Edges fijas: todos los caminos terminan en sintetizar → END
grafo.add_edge("agente_datos", "sintetizar")
grafo.add_edge("agente_rag",   "sintetizar")
grafo.add_edge("sintetizar",   END)

app = grafo.compile()   # ← el grafo queda listo para invocar
```

#### Tipos de edges en LangGraph

| Tipo | Función | Ejemplo |
|------|---------|---------|
| `add_edge(A, B)` | Siempre va de A a B | `sintetizar → END` |
| `add_conditional_edges(A, fn, mapa)` | Llama a `fn(estado)` y va al nodo que devuelva | `supervisor → trm/datos/rag` |

#### Funciones de enrutamiento

```python
def enrutar_desde_supervisor(estado: EstadoMultiagente) -> str:
    ruta = estado.get("ruta", "rag")
    if ruta in ("trm", "multiple"):
        return "agente_trm"    # nombre del nodo destino
    elif ruta == "datos":
        return "agente_datos"
    else:
        return "agente_rag"

def enrutar_desde_trm(estado: EstadoMultiagente) -> str:
    if estado.get("ruta") == "multiple":
        return "agente_rag"    # pregunta cruzada: también consulta RAG
    return "sintetizar"        # pregunta simple TRM: va directo a sintetizar
```

### Las 4 rutas posibles

```
"trm":      START → supervisor → agente_trm → sintetizar → END
"datos":    START → supervisor → agente_datos → sintetizar → END
"rag":      START → supervisor → agente_rag → sintetizar → END
"multiple": START → supervisor → agente_trm → agente_rag → sintetizar → END
```

### Visualizar el grafo

```bash
python agente_langgraph.py --grafo
# Genera: grafo_multiagente.png
```

### Probar el agente desde la terminal

```bash
# Ruta "trm"
python agente_langgraph.py --pregunta "¿Cuánto está el dólar en diciembre 2024?"

# Ruta "datos"
python agente_langgraph.py --pregunta "¿Cuál es el déficit comercial de Colombia en 2024?"

# Ruta "rag"
python agente_langgraph.py --pregunta "¿Cuál fue la tasa de desempleo en el tercer trimestre?"

# Ruta "multiple"
python agente_langgraph.py --pregunta "¿Cómo relaciona el TRM con la inflación y el desempleo?"
```

---

## 4. LangChain vs LangGraph — cuándo usar cada uno

```
Pregunta simple:
  "¿Cuánto está el dólar?"
       ↓ ambos responden bien
  LangChain: TRM usa obtener_trm_actual() → respuesta directa
  LangGraph: supervisor → "trm" → agente_trm → sintetizar

Pregunta cruzada:
  "¿Cómo afecta la inflación al TRM y qué sectores exportadores sufren más?"
       ↓
  LangChain: el LLM decide combinar buscar_documentos_dane + obtener_trm_actual +
             analizar_sectores_exportacion en el mismo ciclo ReAct
  LangGraph: supervisor → "multiple" → agente_trm + agente_rag → sintetizar
             (más ordenado, cada especialista trabaja en su dominio)
```

La interfaz web permite seleccionar cuál backend usar en cada consulta,
lo que facilita comparar ambas implementaciones con la misma pregunta.

---

## 5. El campo `temperatura` del LLM

Los agentes usan distintas temperaturas según su rol:

| Nodo | Temperatura | Razón |
|------|-------------|-------|
| Supervisor | 0.0 | Debe ser determinista: siempre elige la misma ruta para la misma pregunta |
| Especialistas | 0.1 | Mínima creatividad para interpretar datos numéricos |
| Sintetizador | 0.3 | Algo más de fluidez para redactar la respuesta final |
| Agente ReAct (LangChain) | 0.2 | Balance entre precisión y naturalidad |

La temperatura controla qué tan "creativo" es el LLM:
- `0.0` = siempre elige el token más probable (determinista).
- `1.0` = respuestas variadas y más creativas.

---

## Referencias

1. LangGraph — `create_react_agent` (prebuilt).
   https://langchain-ai.github.io/langgraph/reference/prebuilt/

2. LangGraph — StateGraph y nodos.
   https://langchain-ai.github.io/langgraph/concepts/low_level/

3. LangGraph — Conditional Edges.
   https://langchain-ai.github.io/langgraph/how-tos/branching/

4. LangChain — System messages y prompts.
   https://python.langchain.com/docs/concepts/messages/

5. Python — TypedDict.
   https://docs.python.org/3/library/typing.html#typing.TypedDict

6. Patrón multi-agente Supervisor.
   https://langchain-ai.github.io/langgraph/concepts/multi_agent/

---

## Pasos Git

```bash
git add agente_langchain.py agente_langgraph.py tutorial_AgenteIA/06_agentes.md
git commit -m "feat: agrega agentes langchain y langgraph, y documento 06"
git push origin main
```

> **Siguiente documento:** `07_api_pipeline.md` — El servidor FastAPI,
> el pipeline de medición de métricas, la base de datos SQLite y el
> middleware de logging.
