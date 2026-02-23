"""
agente_langgraph.py — Sistema Multi-Agente con LangGraph (Supervisor + 3 Especialistas)
========================================================================================
Proyecto agente_IA_TRM · USB Medellín

Un SUPERVISOR analiza la pregunta y decide qué agente(s) especialistas consultar.
Cada especialista tiene sus propias herramientas y ejecuta su propio ciclo ReAct.
Un nodo SINTETIZADOR integra todas las respuestas en una respuesta final.

FLUJO DEL GRAFO:

  START
    ↓
  [supervisor]     → clasifica la pregunta: ruta = "trm"|"datos"|"rag"|"multiple"
    ↓ (según ruta)
  [agente_trm]     → ReAct con TOOLS_TRM    (si ruta es "trm" o "multiple")
  [agente_datos]   → ReAct con TOOLS_DATOS  (si ruta es "datos")
  [agente_rag]     → ReAct con TOOLS_RAG    (si ruta es "rag" o "multiple")
    ↓
  [sintetizar]     → combina todas las respuestas disponibles
    ↓
  END

Uso desde línea de comandos:
  python agente_langgraph.py
  python agente_langgraph.py --pregunta "¿Cuánto está el dólar?"
  python agente_langgraph.py --pregunta "¿Qué exporta Colombia y cómo impacta el TRM?"
  python agente_langgraph.py --grafo    # genera grafo_multiagente.png
"""

import sys
import json
import argparse
from typing import TypedDict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
import tools as agent_tools


# ---------------------------------------------------------------------------
# Prompts por defecto — editables desde la UI Bootstrap
# ---------------------------------------------------------------------------

PROMPT_SUPERVISOR = (
    "Eres un enrutador de consultas económicas. Clasifica la pregunta en UNA de estas rutas:\n\n"
    "  'trm'      → solo sobre tipo de cambio: dólar, TRM, devaluación, variación del peso\n"
    "  'datos'    → solo sobre comercio exterior: exportaciones, importaciones, balanza, sectores\n"
    "  'rag'      → solo sobre estadísticas DANE: desempleo, inflación, PIB, población, censo\n"
    "  'multiple' → combina TRM+DANE, o TRM+exportaciones con contexto macro\n\n"
    "Responde EXACTAMENTE con este JSON (sin markdown):\n"
    "{\"ruta\": \"<ruta>\", \"justificacion\": \"<una oración breve>\"}"
)

PROMPT_TRM = (
    "Eres un analista de mercado cambiario especializado en el peso colombiano. "
    "Responde preguntas sobre el TRM (tipo de cambio dolar/peso) usando las herramientas disponibles. "
    "Siempre menciona el valor exacto del TRM, la tendencia y una interpretacion economica breve. "
    "Responde en español, conciso y con datos precisos."
)

PROMPT_DATOS = (
    "Eres un analista de comercio exterior de Colombia. "
    "Responde preguntas sobre exportaciones, importaciones y balanza comercial del 2024. "
    "Destaca los sectores mas importantes, el deficit/superavit y tendencias clave. "
    "Usa datos exactos de las herramientas. Responde en español."
)

PROMPT_RAG = (
    "Eres un investigador especializado en estadisticas del DANE Colombia. "
    "Responde preguntas buscando en los reportes disponibles: desempleo, IPC, PIB y censo. "
    "Llama primero a listar_reportes_dane() para conocer las fuentes, luego "
    "buscar_documentos_dane() con terminos relevantes para encontrar la informacion. "
    "Cita los documentos fuente y los valores exactos encontrados. Responde en español."
)

PROMPT_SINTETIZADOR = (
    "Eres un analista económico que integra información de múltiples fuentes. "
    "Recibes respuestas de agentes especializados y debes sintetizarlas en "
    "una respuesta única, coherente y bien estructurada en español. "
    "Organiza la respuesta con secciones claras si hay múltiples temas. "
    "Incluye una conclusión que relacione los diferentes aspectos si aplica. "
    "Cita los números exactos mencionados por los agentes."
)


# ---------------------------------------------------------------------------
# Estado compartido del grafo
# ---------------------------------------------------------------------------

class EstadoMultiagente(TypedDict):
    """
    El estado fluye por todos los nodos del grafo.
    Cada nodo lee los campos que necesita y retorna solo los que modifica.
    LangGraph hace el merge automático después de cada nodo.

    ruta: decide qué agente(s) consultar:
        "trm"      → solo el agente de tipo de cambio
        "datos"    → solo el agente de comercio exterior
        "rag"      → solo el agente de documentos DANE
        "multiple" → agente TRM + agente RAG (pregunta cruzada)

    prompts: dict con prompts personalizados para esta ejecución.
        Claves: supervisor, trm, datos, rag, sintetizador
        Si una clave no existe, el nodo usa su constante de módulo.
    """
    pregunta:        str
    ruta:            str
    justificacion:   str
    resp_trm:        str
    resp_datos:      str
    resp_rag:        str
    respuesta_final: str
    prompts:         dict


# ---------------------------------------------------------------------------
# Nodo 1: Supervisor — clasifica la pregunta y decide la ruta
# ---------------------------------------------------------------------------

def nodo_supervisor(estado: EstadoMultiagente) -> dict:
    """
    Analiza la pregunta y determina qué agente(s) son los más adecuados.
    El supervisor NO responde la pregunta — solo enruta.
    """
    print("[SUPERVISOR] Analizando pregunta y eligiendo ruta...")

    from langchain_core.messages import HumanMessage, SystemMessage
    llm = config.crear_llm_dinamico(temperature=0)

    prompt_sv = estado.get("prompts", {}).get("supervisor") or PROMPT_SUPERVISOR
    messages = [
        SystemMessage(content=prompt_sv),
        HumanMessage(content=f"Pregunta: {estado['pregunta']}"),
    ]

    respuesta = llm.invoke(messages)
    texto     = respuesta.content.strip()

    # Eliminar bloques de código markdown si el LLM los agregó
    if "```" in texto:
        lineas = texto.split("\n")
        texto  = "\n".join(ln for ln in lineas if not ln.strip().startswith("```")).strip()

    try:
        datos = json.loads(texto)
        ruta  = datos.get("ruta", "rag").lower()
        just  = datos.get("justificacion", "")
    except (json.JSONDecodeError, AttributeError):
        ruta = "rag"
        for r in ("trm", "datos", "multiple"):
            if r in texto.lower():
                ruta = r
                break
        just = texto[:100]

    if ruta not in ("trm", "datos", "rag", "multiple"):
        ruta = "rag"

    print(f"  Ruta elegida : '{ruta}'")
    print(f"  Justificacion: {just}")

    return {"ruta": ruta, "justificacion": just}


# ---------------------------------------------------------------------------
# Nodo 2: Agente TRM — especialista en tipo de cambio
# ---------------------------------------------------------------------------

def nodo_agente_trm(estado: EstadoMultiagente) -> dict:
    """Especialista en TRM. Tiene acceso exclusivo a TOOLS_TRM."""
    print("[AGENTE TRM] Consultando tipo de cambio...")

    llm = config.crear_llm_dinamico(temperature=0.1)
    system_trm = estado.get("prompts", {}).get("trm") or PROMPT_TRM

    try:
        from langchain.agents import create_agent
        sub_agente = create_agent(model=llm, tools=agent_tools.TOOLS_TRM, system_prompt=system_trm)
        resultado  = sub_agente.invoke({"messages": [("user", estado["pregunta"])]})
    except (ImportError, AttributeError):
        from langgraph.prebuilt import create_react_agent
        sub_agente = create_react_agent(model=llm, tools=agent_tools.TOOLS_TRM,
                                        state_modifier=system_trm)
        resultado  = sub_agente.invoke({"messages": [("user", estado["pregunta"])]})

    respuesta = resultado["messages"][-1].content
    print(f"  TRM respondido ({len(respuesta)} chars)")
    return {"resp_trm": respuesta}


# ---------------------------------------------------------------------------
# Nodo 3: Agente Datos — especialista en comercio exterior
# ---------------------------------------------------------------------------

def nodo_agente_datos(estado: EstadoMultiagente) -> dict:
    """Especialista en comercio exterior. Tiene acceso exclusivo a TOOLS_DATOS."""
    print("[AGENTE DATOS] Analizando comercio exterior...")

    llm = config.crear_llm_dinamico(temperature=0.1)
    system_datos = estado.get("prompts", {}).get("datos") or PROMPT_DATOS

    try:
        from langchain.agents import create_agent
        sub_agente = create_agent(model=llm, tools=agent_tools.TOOLS_DATOS, system_prompt=system_datos)
        resultado  = sub_agente.invoke({"messages": [("user", estado["pregunta"])]})
    except (ImportError, AttributeError):
        from langgraph.prebuilt import create_react_agent
        sub_agente = create_react_agent(model=llm, tools=agent_tools.TOOLS_DATOS,
                                        state_modifier=system_datos)
        resultado  = sub_agente.invoke({"messages": [("user", estado["pregunta"])]})

    respuesta = resultado["messages"][-1].content
    print(f"  Datos respondidos ({len(respuesta)} chars)")
    return {"resp_datos": respuesta}


# ---------------------------------------------------------------------------
# Nodo 4: Agente RAG — especialista en documentos DANE
# ---------------------------------------------------------------------------

def nodo_agente_rag(estado: EstadoMultiagente) -> dict:
    """Especialista en reportes DANE. Tiene acceso exclusivo a TOOLS_RAG."""
    print("[AGENTE RAG] Buscando en documentos DANE...")

    llm = config.crear_llm_dinamico(temperature=0.1)
    system_rag = estado.get("prompts", {}).get("rag") or PROMPT_RAG

    try:
        from langchain.agents import create_agent
        sub_agente = create_agent(model=llm, tools=agent_tools.TOOLS_RAG, system_prompt=system_rag)
        resultado  = sub_agente.invoke({"messages": [("user", estado["pregunta"])]})
    except (ImportError, AttributeError):
        from langgraph.prebuilt import create_react_agent
        sub_agente = create_react_agent(model=llm, tools=agent_tools.TOOLS_RAG,
                                        state_modifier=system_rag)
        resultado  = sub_agente.invoke({"messages": [("user", estado["pregunta"])]})

    respuesta = resultado["messages"][-1].content
    print(f"  RAG respondido ({len(respuesta)} chars)")
    return {"resp_rag": respuesta}


# ---------------------------------------------------------------------------
# Nodo 5: Sintetizador — integra todas las respuestas
# ---------------------------------------------------------------------------

def nodo_sintetizar(estado: EstadoMultiagente) -> dict:
    """Recibe las respuestas de los agentes y elabora una respuesta final coherente."""
    print("[SINTETIZADOR] Integrando respuestas...")

    from langchain_core.messages import HumanMessage, SystemMessage

    partes = []
    if estado.get("resp_trm"):
        partes.append(f"=== AGENTE TRM ===\n{estado['resp_trm']}")
    if estado.get("resp_datos"):
        partes.append(f"=== AGENTE DATOS ===\n{estado['resp_datos']}")
    if estado.get("resp_rag"):
        partes.append(f"=== AGENTE RAG ===\n{estado['resp_rag']}")

    contexto    = "\n\n".join(partes)
    agentes_str = ", ".join(
        a for a, r in [("TRM",   estado.get("resp_trm")),
                       ("Datos", estado.get("resp_datos")),
                       ("RAG",   estado.get("resp_rag"))]
        if r
    )

    llm = config.crear_llm_dinamico(temperature=0.3)
    prompt_sint = estado.get("prompts", {}).get("sintetizador") or PROMPT_SINTETIZADOR
    messages = [
        SystemMessage(content=prompt_sint),
        HumanMessage(content=(
            f"Pregunta original: {estado['pregunta']}\n\n"
            f"Agentes consultados: {agentes_str}\n\n"
            f"Respuestas de los agentes:\n\n{contexto}\n\n"
            "Sintetiza una respuesta final clara y completa:"
        )),
    ]

    respuesta = llm.invoke(messages)
    print("  Síntesis completada")
    return {"respuesta_final": respuesta.content}


# ---------------------------------------------------------------------------
# Edges condicionales — lógica de ruteo
# ---------------------------------------------------------------------------

def enrutar_desde_supervisor(estado: EstadoMultiagente) -> str:
    ruta = estado.get("ruta", "rag")
    if ruta in ("trm", "multiple"):
        return "agente_trm"
    elif ruta == "datos":
        return "agente_datos"
    else:
        return "agente_rag"


def enrutar_desde_trm(estado: EstadoMultiagente) -> str:
    if estado.get("ruta") == "multiple":
        return "agente_rag"
    return "sintetizar"


# ---------------------------------------------------------------------------
# Construir el grafo
# ---------------------------------------------------------------------------

def construir_grafo():
    """Ensambla y compila el StateGraph multi-agente."""
    from langgraph.graph import StateGraph, START, END

    grafo = StateGraph(EstadoMultiagente)

    grafo.add_node("supervisor",   nodo_supervisor)
    grafo.add_node("agente_trm",   nodo_agente_trm)
    grafo.add_node("agente_datos", nodo_agente_datos)
    grafo.add_node("agente_rag",   nodo_agente_rag)
    grafo.add_node("sintetizar",   nodo_sintetizar)

    grafo.add_edge(START, "supervisor")

    grafo.add_conditional_edges(
        "supervisor",
        enrutar_desde_supervisor,
        {
            "agente_trm":   "agente_trm",
            "agente_datos": "agente_datos",
            "agente_rag":   "agente_rag",
        },
    )

    grafo.add_conditional_edges(
        "agente_trm",
        enrutar_desde_trm,
        {
            "agente_rag": "agente_rag",
            "sintetizar": "sintetizar",
        },
    )

    grafo.add_edge("agente_datos", "sintetizar")
    grafo.add_edge("agente_rag",   "sintetizar")
    grafo.add_edge("sintetizar",   END)

    return grafo.compile()


# ---------------------------------------------------------------------------
# Función principal de ejecución
# ---------------------------------------------------------------------------

def ejecutar_agente(pregunta: str, silencioso: bool = False,
                    prompts: dict | None = None) -> str:
    """
    Ejecuta el sistema multi-agente con la pregunta dada.

    Parámetros:
        pregunta:   texto de la pregunta
        silencioso: si True, suprime el encabezado
        prompts:    dict con prompts personalizados (claves: supervisor, trm, datos, rag, sintetizador)
                    Si None, carga desde SQLite o usa los defaults del módulo.

    Retorna:
        str con la respuesta final sintetizada
    """
    # Prioridad de prompts: parámetro > SQLite > constantes del módulo
    if prompts is None:
        try:
            import database
            todos   = database.get_all_prompts()
            prompts = {k.replace("langgraph_", ""): v
                       for k, v in todos.items() if k.startswith("langgraph_")}
        except Exception:
            prompts = {}

    app = construir_grafo()

    if not silencioso:
        print(f"\n{'='*65}")
        print(f"  SISTEMA MULTI-AGENTE — LangGraph  (agente_IA_TRM)")
        print(f"{'='*65}")
        print(f"  Pregunta   : {pregunta}")
        print(f"  LLM        : {config.LLM_PROVIDER} / {config.LLM_MODEL}")
        print(f"  Agentes    : Supervisor + TRM + Datos + RAG + Sintetizador")
        print(f"  Prompts    : {'personalizados' if prompts else 'defaults'}")
        print(f"{'='*65}\n")

    estado_inicial: EstadoMultiagente = {
        "pregunta":        pregunta,
        "ruta":            "",
        "justificacion":   "",
        "resp_trm":        "",
        "resp_datos":      "",
        "resp_rag":        "",
        "respuesta_final": "",
        "prompts":         prompts or {},
    }

    estado_final = app.invoke(estado_inicial)

    if not silencioso:
        print(f"\n{'='*65}")
        print("  RESPUESTA FINAL")
        print(f"{'='*65}")
        print(estado_final["respuesta_final"])
        print(f"\n  Ruta: {estado_final['ruta']} — {estado_final['justificacion']}")
        print(f"{'='*65}\n")

    return estado_final["respuesta_final"]


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

PREGUNTA_DEFAULT = (
    "¿Cuál es el TRM actual y cómo se relaciona con la inflación "
    "y el desempleo registrados por el DANE en 2024?"
)


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Multi-Agente LangGraph · agente_IA_TRM"
    )
    parser.add_argument(
        "--pregunta",
        default=PREGUNTA_DEFAULT,
        help="Pregunta económica (puede combinar TRM, comercio exterior y estadísticas DANE)",
    )
    parser.add_argument(
        "--grafo",
        action="store_true",
        help="Genera grafo_multiagente.png con la visualización del grafo",
    )
    args = parser.parse_args()

    config.validate()

    if args.grafo:
        app = construir_grafo()
        try:
            img_bytes = app.get_graph().draw_mermaid_png()
            with open("grafo_multiagente.png", "wb") as f:
                f.write(img_bytes)
            print("Grafo guardado en: grafo_multiagente.png")
        except Exception as e:
            print(f"No se pudo generar el grafo: {e}")
        return

    ejecutar_agente(pregunta=args.pregunta)


if __name__ == "__main__":
    main()
