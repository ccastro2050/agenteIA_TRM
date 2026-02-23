"""
middleware.py — Registro de consultas, costos y latencia
=========================================================
Proyecto agente_IA_TRM · USB Medellín

Responsabilidades:
  1. Estimar tokens (input / output) a partir de longitud de texto
  2. Calcular costo estimado en USD según el proveedor LLM activo
  3. Guardar cada consulta en logs/consultas.jsonl (backup legible)
  4. Exponer métricas operativas: latencia p50/p95/p99, costos, totales

Formato del log JSONL (una línea JSON por consulta):
  {"timestamp": "...", "pregunta": "...", "respuesta": "...",
   "latencia_ms": 1234, "tokens_in": 50, "tokens_out": 200,
   "costo_usd": 0.0035, "modelo": "openai/gpt-4o-mini"}
"""

import json
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
import database

LOGS_FILE: Path = config.LOGS_DIR / "consultas.jsonl"


# ---------------------------------------------------------------------------
# Estimación de tokens
# ---------------------------------------------------------------------------

def estimar_tokens(texto: str) -> int:
    """
    Estimación aproximada de tokens a partir de caracteres.
    Regla práctica: ~4 chars por token (inglés/español mezclado).
    """
    return max(1, len(texto) // 4)


# ---------------------------------------------------------------------------
# Cálculo de costo
# ---------------------------------------------------------------------------

def calcular_costo(tokens_in: int, tokens_out: int) -> float:
    """
    Estima el costo en USD de una consulta según el proveedor LLM activo.
    Usa la tabla COSTOS_POR_PROVEEDOR de config.py.
    Los precios son por 1 000 tokens.
    """
    costos = config.COSTOS_POR_PROVEEDOR.get(
        config.LLM_PROVIDER,
        {"input": 0.001, "output": 0.003}
    )
    return (tokens_in * costos["input"] + tokens_out * costos["output"]) / 1000


# ---------------------------------------------------------------------------
# Registro de consultas
# ---------------------------------------------------------------------------

def registrar_consulta(
    pregunta:    str,
    respuesta:   str,
    latencia_ms: float,
    tokens_in:   int,
    tokens_out:  int,
    costo_usd:   float,
    backend:     str = "langgraph",
) -> None:
    """
    Guarda un registro de la consulta en:
      1. SQLite (agente_config.db) — BD operacional principal
      2. logs/consultas.jsonl      — backup legible / exportable
    """
    ts = datetime.now().isoformat()
    # Proveedor/modelo dinámico (SQLite > .env)
    try:
        db_cfg   = database.get_all_config()
        provider = db_cfg.get("llm_provider", "") or config.LLM_PROVIDER
        model    = db_cfg.get("llm_model",    "") or config.LLM_MODEL
    except Exception:
        provider = config.LLM_PROVIDER
        model    = config.LLM_MODEL
    modelo = f"{provider}/{model}"

    # 1. SQLite — fuente primaria
    try:
        database.save_consulta(
            timestamp=ts, pregunta=pregunta, respuesta=respuesta,
            latencia_ms=round(latencia_ms, 1),
            tokens_in=tokens_in, tokens_out=tokens_out,
            costo_usd=round(costo_usd, 6),
            modelo=modelo, backend=backend,
        )
    except Exception:
        pass  # no bloquear la respuesta si SQLite falla

    # 2. JSONL — backup / exportación
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    registro = {
        "timestamp":   ts,
        "pregunta":    pregunta,
        "respuesta":   respuesta,
        "latencia_ms": round(latencia_ms, 1),
        "tokens_in":   tokens_in,
        "tokens_out":  tokens_out,
        "costo_usd":   round(costo_usd, 6),
        "modelo":      modelo,
        "backend":     backend,
    }
    with open(LOGS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Lectura de logs
# ---------------------------------------------------------------------------

def leer_logs(n: int | None = None) -> list[dict]:
    """Lee todos los registros del archivo JSONL."""
    if not LOGS_FILE.exists():
        return []

    registros = []
    with open(LOGS_FILE, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                try:
                    registros.append(json.loads(linea))
                except json.JSONDecodeError:
                    pass

    if n is not None:
        registros = registros[-n:]
    return registros


# ---------------------------------------------------------------------------
# Métricas operativas
# ---------------------------------------------------------------------------

def calcular_metricas() -> dict:
    """Calcula métricas operativas desde SQLite. Fallback a JSONL."""
    metricas = database.get_metricas_consultas()
    if not metricas.get("sin_datos"):
        return metricas

    registros = leer_logs()
    if not registros:
        return {
            "sin_datos": True,
            "mensaje": "No hay consultas registradas. Haz consultas a la API para ver métricas.",
        }

    n = len(registros)
    latencias  = sorted(r["latencia_ms"] for r in registros)
    costos     = [r["costo_usd"]  for r in registros]
    tokens_in  = [r.get("tokens_in",  0) for r in registros]
    tokens_out = [r.get("tokens_out", 0) for r in registros]

    def percentil(lista: list, p: float) -> float:
        idx = max(0, int(len(lista) * p / 100) - 1)
        return round(lista[idx], 1)

    total_in  = sum(tokens_in)
    total_out = sum(tokens_out)
    total_tok = total_in + total_out
    costo_tot = sum(costos)

    modelos: dict[str, int] = {}
    for r in registros:
        m = r.get("modelo", "desconocido")
        modelos[m] = modelos.get(m, 0) + 1

    return {
        "total_consultas":      n,
        "latencia_promedio_ms": round(sum(latencias) / n, 1),
        "latencia_p50_ms":      percentil(latencias, 50),
        "latencia_p95_ms":      percentil(latencias, 95),
        "latencia_p99_ms":      percentil(latencias, 99),
        "latencia_min_ms":      round(latencias[0], 1),
        "latencia_max_ms":      round(latencias[-1], 1),
        "tokens_in_total":      total_in,
        "tokens_out_total":     total_out,
        "tokens_total":         total_tok,
        "costo_total_usd":      round(costo_tot, 4),
        "costo_promedio_usd":   round(costo_tot / n, 6),
        "costo_por_mil_tokens": round(costo_tot / max(total_tok, 1) * 1000, 4),
        "consultas_por_modelo": modelos,
        "primera_consulta":     registros[0]["timestamp"],
        "ultima_consulta":      registros[-1]["timestamp"],
    }


def obtener_historial(n: int = 10) -> list[dict]:
    """Retorna las últimas n consultas desde SQLite. Fallback a JSONL."""
    registros = database.get_historial(n=n)

    if not registros:
        registros_jsonl = leer_logs(n=n)
        return [
            {
                "timestamp":   r["timestamp"],
                "pregunta":    r["pregunta"][:80] + ("..." if len(r["pregunta"]) > 80 else ""),
                "latencia_ms": r["latencia_ms"],
                "tokens_out":  r.get("tokens_out", 0),
                "costo_usd":   r["costo_usd"],
                "modelo":      r.get("modelo", ""),
                "backend":     r.get("backend", "langgraph"),
            }
            for r in reversed(registros_jsonl)
        ]

    return [
        {
            "timestamp":   r["timestamp"],
            "pregunta":    r["pregunta"][:80] + ("..." if len(r["pregunta"]) > 80 else ""),
            "latencia_ms": r["latencia_ms"],
            "tokens_out":  r.get("tokens_out", 0),
            "costo_usd":   r["costo_usd"],
            "modelo":      r.get("modelo", ""),
            "backend":     r.get("backend", "langgraph"),
        }
        for r in registros
    ]
