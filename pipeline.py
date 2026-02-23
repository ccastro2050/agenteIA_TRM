"""
pipeline.py — Pipeline de producción con LangGraph
===================================================
Proyecto agente_IA_TRM · USB Medellín

Define el grafo LangGraph que procesa cada request.
Soporta dos backends de agente:
  - "langchain" → agente_langchain.py (ReAct con todas las tools)
  - "langgraph" → agente_langgraph.py (Supervisor + 3 especialistas)

Arquitectura (3 nodos lineales):
  START
    ↓
  nodo_ejecutar_agente   → llama al agente seleccionado
    ↓
  nodo_calcular_metricas → estima tokens y costo USD
    ↓
  nodo_registrar         → guarda en SQLite y logs/consultas.jsonl
    ↓
  END
"""

import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime
from typing import TypedDict

from langgraph.graph import StateGraph, END

import middleware
import config


def _modelo_activo() -> str:
    """Retorna 'provider/model' usando la config dinámica (SQLite > .env)."""
    try:
        import database
        db_cfg   = database.get_all_config()
        provider = db_cfg.get("llm_provider", "") or config.LLM_PROVIDER
        model    = db_cfg.get("llm_model",    "") or config.LLM_MODEL
        return f"{provider}/{model}"
    except Exception:
        return f"{config.LLM_PROVIDER}/{config.LLM_MODEL}"


# ---------------------------------------------------------------------------
# Estado del pipeline
# ---------------------------------------------------------------------------

class EstadoConsulta(TypedDict):
    """Estado compartido entre los nodos del pipeline."""
    pregunta:    str
    backend:     str    # "langchain" | "langgraph"
    temperatura: float
    prompts:     dict   # prompts para esta ejecución
    respuesta:   str
    latencia_ms: float
    tokens_in:   int
    tokens_out:  int
    costo_usd:   float
    timestamp:   str


# ---------------------------------------------------------------------------
# Nodos del pipeline
# ---------------------------------------------------------------------------

def nodo_ejecutar_agente(estado: EstadoConsulta) -> dict:
    """Nodo 1: Invoca el agente seleccionado y mide la latencia."""
    inicio      = time.time()
    backend     = estado.get("backend", "langgraph")
    prompts_raw = estado.get("prompts") or {}

    if backend == "langchain":
        import agente_langchain
        system_prompt = prompts_raw.get("langchain_main") or None
        respuesta = agente_langchain.ejecutar_agente(
            pregunta=estado["pregunta"], silencioso=True,
            system_prompt=system_prompt,
        )
    else:
        import agente_langgraph
        lg_prompts = {k.replace("langgraph_", ""): v
                      for k, v in prompts_raw.items()
                      if k.startswith("langgraph_")} or None
        respuesta = agente_langgraph.ejecutar_agente(
            pregunta=estado["pregunta"], silencioso=True,
            prompts=lg_prompts,
        )

    latencia_ms = (time.time() - inicio) * 1000

    return {
        "respuesta":   respuesta,
        "latencia_ms": round(latencia_ms, 1),
        "timestamp":   datetime.now().isoformat(),
    }


def nodo_calcular_metricas(estado: EstadoConsulta) -> dict:
    """Nodo 2: Estima tokens y calcula el costo USD del request."""
    tokens_in  = middleware.estimar_tokens(estado["pregunta"])
    tokens_out = middleware.estimar_tokens(estado["respuesta"])
    costo_usd  = middleware.calcular_costo(tokens_in, tokens_out)

    return {
        "tokens_in":  tokens_in,
        "tokens_out": tokens_out,
        "costo_usd":  round(costo_usd, 6),
    }


def nodo_registrar(estado: EstadoConsulta) -> dict:
    """Nodo 3: Persiste el registro en SQLite y logs/consultas.jsonl."""
    middleware.registrar_consulta(
        pregunta=estado["pregunta"],
        respuesta=estado["respuesta"],
        latencia_ms=estado["latencia_ms"],
        tokens_in=estado["tokens_in"],
        tokens_out=estado["tokens_out"],
        costo_usd=estado["costo_usd"],
        backend=estado.get("backend", "langgraph"),
    )
    return {}


# ---------------------------------------------------------------------------
# Construir el grafo
# ---------------------------------------------------------------------------

def construir_pipeline():
    """Construye y compila el grafo de producción."""
    grafo = StateGraph(EstadoConsulta)

    grafo.add_node("ejecutar_agente",   nodo_ejecutar_agente)
    grafo.add_node("calcular_metricas", nodo_calcular_metricas)
    grafo.add_node("registrar",         nodo_registrar)

    grafo.set_entry_point("ejecutar_agente")
    grafo.add_edge("ejecutar_agente",   "calcular_metricas")
    grafo.add_edge("calcular_metricas", "registrar")
    grafo.add_edge("registrar",         END)

    return grafo.compile()


_pipeline_app = None


def obtener_pipeline():
    global _pipeline_app
    if _pipeline_app is None:
        _pipeline_app = construir_pipeline()
    return _pipeline_app


# ---------------------------------------------------------------------------
# Función de alto nivel — usada por main.py
# ---------------------------------------------------------------------------

def procesar_consulta(pregunta: str, temperatura: float = 0.2,
                      backend: str = "langgraph",
                      prompts: dict | None = None) -> dict:
    """
    Procesa una consulta pasándola por el pipeline completo.

    Retorna dict con: respuesta, latencia_ms, tokens_in, tokens_out,
                      costo_usd, timestamp, modelo, backend
    """
    app = obtener_pipeline()

    estado_inicial: EstadoConsulta = {
        "pregunta":    pregunta,
        "backend":     backend,
        "temperatura": temperatura,
        "prompts":     prompts or {},
        "respuesta":   "",
        "latencia_ms": 0.0,
        "tokens_in":   0,
        "tokens_out":  0,
        "costo_usd":   0.0,
        "timestamp":   "",
    }

    estado_final = app.invoke(estado_inicial)

    return {
        "respuesta":    estado_final["respuesta"],
        "latencia_ms":  estado_final["latencia_ms"],
        "tokens_in":    estado_final["tokens_in"],
        "tokens_out":   estado_final["tokens_out"],
        "tokens_total": estado_final["tokens_in"] + estado_final["tokens_out"],
        "costo_usd":    estado_final["costo_usd"],
        "timestamp":    estado_final["timestamp"],
        "modelo":       _modelo_activo(),
        "backend":      backend,
    }


# ---------------------------------------------------------------------------
# Punto de entrada (prueba directa)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--backend",  default="langgraph", choices=["langchain", "langgraph"])
    parser.add_argument("--pregunta", default="¿Cuánto está el dólar en Colombia?")
    args = parser.parse_args()

    config.validate()
    print(f"\nBackend: {args.backend}")
    resultado = procesar_consulta(args.pregunta, backend=args.backend)
    print(f"Latencia: {resultado['latencia_ms']:.0f}ms | "
          f"Costo: ${resultado['costo_usd']:.4f} | "
          f"Tokens: {resultado['tokens_total']}")
