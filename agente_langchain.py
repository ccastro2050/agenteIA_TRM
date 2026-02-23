"""
agente_langchain.py — Agente ReAct con LangChain
=================================================
Proyecto agente_IA_TRM · USB Medellín

El agente usa el patrón ReAct para razonar sobre QUÉ herramientas usar:
  - Pregunta sobre el dólar       → usa TOOLS_TRM
  - Pregunta sobre exportaciones  → usa TOOLS_DATOS
  - Pregunta sobre DANE           → usa TOOLS_RAG
  - Pregunta cruzada              → combina herramientas de múltiples dominios

Diferencia clave con agente_langgraph.py:
  agente_langchain.py  → el LLM decide libremente qué herramientas usar
  agente_langgraph.py  → el grafo programa el ruteo entre sub-agentes

Uso desde línea de comandos:
    python agente_langchain.py
    python agente_langchain.py --pregunta "¿Cuánto está el dólar hoy?"
    python agente_langchain.py --pregunta "¿Cuáles son los principales productos que exporta Colombia?"
"""

import sys
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
import tools as agent_tools


# ---------------------------------------------------------------------------
# System prompt del agente
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Eres un analista económico de Colombia con acceso a tres dominios de información:

1. TIPO DE CAMBIO (TRM)
   - obtener_trm_actual()          → TRM vigente en diciembre 2024 y variación mensual
   - analizar_historico_trm(meses) → tendencia del dólar en los últimos N meses

2. COMERCIO EXTERIOR
   - consultar_balanza_comercial()       → exportaciones vs importaciones mensuales 2024
   - analizar_sectores_exportacion()     → sectores exportadores y su participación

3. DOCUMENTOS DANE (requiere índice vectorial — ejecutar preparar_base.py)
   - listar_reportes_dane()              → catálogo de reportes disponibles
   - buscar_documentos_dane(query, k)    → búsqueda semántica en reportes de desempleo,
                                           inflación, PIB y censo de población

INSTRUCCIONES:
- Identifica qué dominio(s) necesitas para responder la pregunta.
- Si la pregunta involucra múltiples temas, usa herramientas de varios dominios.
- Llama primero a las herramientas de catálogo (listar_*) cuando no estés seguro.
- Cita siempre los números exactos de las herramientas (no inventes cifras).
- Responde SIEMPRE en español con una conclusión clara al final.
- Para preguntas cruzadas (ej: TRM + inflación), explica la relación entre ambas."""


# ---------------------------------------------------------------------------
# Ejecutar el agente
# ---------------------------------------------------------------------------

def ejecutar_agente(pregunta: str, silencioso: bool = False,
                    system_prompt: str | None = None) -> str:
    """
    Ejecuta el agente ReAct con la pregunta dada.

    Parámetros:
        pregunta:      texto de la pregunta a responder
        silencioso:    si True, suprime los prints del encabezado
        system_prompt: prompt a usar (si None, carga de SQLite o usa el default del módulo)

    Retorna:
        str con la respuesta final del agente
    """
    # Prioridad: parámetro > SQLite > constante del módulo
    if system_prompt is None:
        try:
            import database
            system_prompt = database.get_prompt("langchain_main") or SYSTEM_PROMPT
        except Exception:
            system_prompt = SYSTEM_PROMPT

    # LLM dinámico: lee proveedor/modelo de SQLite si el usuario lo cambió en la UI
    llm   = config.crear_llm_dinamico()
    tools = agent_tools.TOOLS_TODOS

    if not silencioso:
        print(f"\n{'='*65}")
        print(f"  AGENTE ReAct — LangChain  (agente_IA_TRM)")
        print(f"{'='*65}")
        print(f"  Pregunta : {pregunta}")
        print(f"  LLM      : {config.LLM_PROVIDER} / {config.LLM_MODEL}")
        print(f"  Tools    : TRM({len(agent_tools.TOOLS_TRM)}) + "
              f"Datos({len(agent_tools.TOOLS_DATOS)}) + "
              f"RAG({len(agent_tools.TOOLS_RAG)})")
        print(f"{'='*65}\n")

    try:
        from langchain.agents import create_agent
        agente    = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
        resultado = agente.invoke({"messages": [("user", pregunta)]})
        respuesta = resultado["messages"][-1].content
    except (ImportError, AttributeError):
        from langgraph.prebuilt import create_react_agent
        agente    = create_react_agent(model=llm, tools=tools,
                                       state_modifier=system_prompt)
        resultado = agente.invoke({"messages": [("user", pregunta)]})
        respuesta = resultado["messages"][-1].content

    if not silencioso:
        print(f"\n{'='*65}")
        print("  RESPUESTA FINAL")
        print(f"{'='*65}")
        print(respuesta)
        print(f"{'='*65}\n")

    return respuesta


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

PREGUNTA_DEFAULT = (
    "¿Cuál es el TRM actual y cómo afecta a las exportaciones colombianas? "
    "¿Qué sectores se benefician más de un dólar alto?"
)


def main():
    parser = argparse.ArgumentParser(
        description="Agente ReAct LangChain · agente_IA_TRM"
    )
    parser.add_argument(
        "--pregunta",
        default=PREGUNTA_DEFAULT,
        help="Pregunta sobre TRM, comercio exterior o estadísticas DANE",
    )
    args = parser.parse_args()

    config.validate()
    ejecutar_agente(pregunta=args.pregunta)


if __name__ == "__main__":
    main()
