"""
exportar_dashboard.py — Exportar métricas a CSVs para BI
=========================================================
agenteIA_TRM · Agente IA Colombia · USB Medellín

Lee los logs de producción (logs/consultas.jsonl) y genera 4 CSVs
con métricas operativas listas para Power BI, Tableau o Excel.

Archivos generados en resultados/:
  01_consultas_log.csv          Todas las consultas: pregunta, latencia, tokens, costo
  02_metricas_latencia.csv      Percentiles de latencia (p25/p50/p75/p95/p99)
  03_analisis_costos.csv        Costo por proveedor, por día, proyecciones
  04_kpi_produccion.csv         KPI cards para portada del dashboard

Uso:
    python exportar_dashboard.py
    python exportar_dashboard.py --n 50   # solo las últimas 50 consultas
"""

import sys
import json
import argparse
import math
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cargar_logs(n: int | None = None) -> list[dict]:
    """Lee logs/consultas.jsonl y retorna la lista de registros."""
    logs_file = config.LOGS_DIR / "consultas.jsonl"
    if not logs_file.exists():
        return []

    registros = []
    with open(logs_file, "r", encoding="utf-8") as f:
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


def _percentil(valores: list[float], p: float) -> float:
    """Calcula el percentil p de una lista de valores."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    idx = max(0, math.ceil(len(ordenados) * p / 100) - 1)
    return round(ordenados[idx], 1)


def _generar_datos_ejemplo() -> list[dict]:
    """Genera registros de ejemplo si no hay logs reales."""
    import random
    random.seed(42)
    ejemplos = []
    preguntas = [
        "¿Cuánto está el dólar hoy?",
        "¿Cuál fue la inflación en 2024?",
        "¿Cómo está la balanza comercial?",
        "¿Qué sectores exportan más?",
        "¿Cuál es el PIB de Colombia?",
    ]
    for i in range(15):
        lat = random.uniform(4000, 18000)
        tok_in  = random.randint(30, 80)
        tok_out = random.randint(150, 400)
        costo   = (tok_in * 0.003 + tok_out * 0.015) / 1000
        ejemplos.append({
            "timestamp":   f"2024-12-{(i % 28) + 1:02d}T{9 + (i % 8):02d}:00:00",
            "pregunta":    preguntas[i % len(preguntas)],
            "respuesta":   "Respuesta de ejemplo del agente.",
            "latencia_ms": round(lat, 1),
            "tokens_in":   tok_in,
            "tokens_out":  tok_out,
            "costo_usd":   round(costo, 6),
            "modelo":      f"{config.LLM_PROVIDER}/{config.LLM_MODEL}",
        })
    return ejemplos


# ---------------------------------------------------------------------------
# Generadores de CSV
# ---------------------------------------------------------------------------

def generar_01_consultas_log(registros: list[dict], out_dir: Path) -> int:
    """01 — Log completo de consultas."""
    import csv

    ruta = out_dir / "01_consultas_log.csv"
    filas = []
    for r in registros:
        filas.append({
            "timestamp":   r.get("timestamp", ""),
            "pregunta":    r.get("pregunta", "")[:100],
            "latencia_ms": r.get("latencia_ms", 0),
            "tokens_in":   r.get("tokens_in", 0),
            "tokens_out":  r.get("tokens_out", 0),
            "tokens_total": r.get("tokens_in", 0) + r.get("tokens_out", 0),
            "costo_usd":   r.get("costo_usd", 0),
            "modelo":      r.get("modelo", ""),
        })

    if filas:
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            writer.writeheader()
            writer.writerows(filas)

    return len(filas)


def generar_02_metricas_latencia(registros: list[dict], out_dir: Path) -> int:
    """02 — Percentiles de latencia."""
    import csv

    latencias = [r.get("latencia_ms", 0) for r in registros]

    filas = [
        {"metrica": "latencia_min_ms",      "valor": min(latencias) if latencias else 0,
         "descripcion": "Latencia mínima registrada"},
        {"metrica": "latencia_p25_ms",       "valor": _percentil(latencias, 25),
         "descripcion": "Percentil 25 (cuartil inferior)"},
        {"metrica": "latencia_p50_ms",       "valor": _percentil(latencias, 50),
         "descripcion": "Mediana (p50) — latencia típica"},
        {"metrica": "latencia_p75_ms",       "valor": _percentil(latencias, 75),
         "descripcion": "Percentil 75 (cuartil superior)"},
        {"metrica": "latencia_p95_ms",       "valor": _percentil(latencias, 95),
         "descripcion": "Percentil 95 — casos lentos"},
        {"metrica": "latencia_p99_ms",       "valor": _percentil(latencias, 99),
         "descripcion": "Percentil 99 — casos extremos"},
        {"metrica": "latencia_max_ms",       "valor": max(latencias) if latencias else 0,
         "descripcion": "Latencia máxima registrada"},
        {"metrica": "latencia_promedio_ms",  "valor": round(sum(latencias) / len(latencias), 1)
         if latencias else 0,
         "descripcion": "Promedio aritmético"},
        {"metrica": "sla_target_ms",         "valor": 30000,
         "descripcion": "SLA objetivo (30 segundos)"},
        {"metrica": "sla_cumplimiento_pct",
         "valor": round(sum(1 for l in latencias if l <= 30000) / max(len(latencias), 1) * 100, 1),
         "descripcion": "% consultas dentro del SLA"},
    ]

    ruta = out_dir / "02_metricas_latencia.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metrica", "valor", "descripcion"])
        writer.writeheader()
        writer.writerows(filas)

    return len(filas)


def generar_03_analisis_costos(registros: list[dict], out_dir: Path) -> int:
    """03 — Análisis de costos por proveedor y proyecciones."""
    import csv

    costos = [r.get("costo_usd", 0) for r in registros]
    tokens_in  = [r.get("tokens_in", 0) for r in registros]
    tokens_out = [r.get("tokens_out", 0) for r in registros]
    n = len(registros)

    costo_total    = sum(costos)
    costo_promedio = costo_total / n if n > 0 else 0
    tokens_prom    = (sum(tokens_in) + sum(tokens_out)) / n if n > 0 else 0

    costos_proveedor = config.COSTOS_POR_PROVEEDOR.get(
        config.LLM_PROVIDER, {"input": 0.001, "output": 0.003}
    )

    filas = [
        # Datos reales
        {"categoria": "Real",        "metrica": "total_consultas",         "valor": n,
         "unidad": "consultas",      "descripcion": "Total consultas registradas"},
        {"categoria": "Real",        "metrica": "costo_total_usd",         "valor": round(costo_total, 4),
         "unidad": "USD",            "descripcion": "Costo total acumulado"},
        {"categoria": "Real",        "metrica": "costo_promedio_usd",      "valor": round(costo_promedio, 6),
         "unidad": "USD/consulta",   "descripcion": "Costo promedio por consulta"},
        {"categoria": "Real",        "metrica": "tokens_promedio",         "valor": round(tokens_prom, 0),
         "unidad": "tokens",         "descripcion": "Tokens promedio por consulta"},
        # Precios del proveedor
        {"categoria": "Proveedor",   "metrica": "precio_input_por_1k",     "valor": costos_proveedor["input"],
         "unidad": "USD/1K tokens",  "descripcion": f"Precio input — {config.LLM_PROVIDER}"},
        {"categoria": "Proveedor",   "metrica": "precio_output_por_1k",    "valor": costos_proveedor["output"],
         "unidad": "USD/1K tokens",  "descripcion": f"Precio output — {config.LLM_PROVIDER}"},
        # Proyecciones
        {"categoria": "Proyeccion",  "metrica": "costo_100_consultas_usd", "valor": round(costo_promedio * 100, 4),
         "unidad": "USD",            "descripcion": "Costo estimado por 100 consultas/día"},
        {"categoria": "Proyeccion",  "metrica": "costo_1000_consultas_usd","valor": round(costo_promedio * 1000, 2),
         "unidad": "USD",            "descripcion": "Costo estimado por 1000 consultas/mes"},
        {"categoria": "Proyeccion",  "metrica": "costo_mensual_bajo_usd",  "valor": round(costo_promedio * 500, 2),
         "unidad": "USD/mes",        "descripcion": "Proyección mensual (500 consultas/mes)"},
        {"categoria": "Proyeccion",  "metrica": "costo_mensual_alto_usd",  "valor": round(costo_promedio * 5000, 2),
         "unidad": "USD/mes",        "descripcion": "Proyección mensual (5000 consultas/mes)"},
    ]

    ruta = out_dir / "03_analisis_costos.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["categoria", "metrica", "valor", "unidad", "descripcion"])
        writer.writeheader()
        writer.writerows(filas)

    return len(filas)


def generar_04_kpi_produccion(registros: list[dict], out_dir: Path) -> int:
    """04 — KPI cards para portada del dashboard."""
    import csv

    n = len(registros)
    latencias = [r.get("latencia_ms", 0) for r in registros]
    costos    = [r.get("costo_usd", 0) for r in registros]

    lat_p50   = _percentil(latencias, 50)
    costo_tot = round(sum(costos), 4)
    sla_pct   = round(sum(1 for l in latencias if l <= 30000) / max(n, 1) * 100, 1)

    filas = [
        {"kpi": "total_consultas",      "valor": n,
         "formato": "numero",           "descripcion": "Total consultas procesadas"},
        {"kpi": "latencia_p50_ms",      "valor": lat_p50,
         "formato": "ms",               "descripcion": "Latencia mediana (p50)"},
        {"kpi": "latencia_p95_ms",      "valor": _percentil(latencias, 95),
         "formato": "ms",               "descripcion": "Latencia p95 (95% de requests)"},
        {"kpi": "sla_cumplimiento_pct", "valor": sla_pct,
         "formato": "porcentaje",       "descripcion": "% consultas dentro de SLA (30s)"},
        {"kpi": "costo_total_usd",      "valor": costo_tot,
         "formato": "USD",              "descripcion": "Costo total acumulado"},
        {"kpi": "costo_promedio_usd",   "valor": round(sum(costos) / max(n, 1), 6),
         "formato": "USD",              "descripcion": "Costo promedio por consulta"},
        {"kpi": "llm_provider",         "valor": config.LLM_PROVIDER,
         "formato": "texto",            "descripcion": "Proveedor LLM activo"},
        {"kpi": "llm_model",            "valor": config.LLM_MODEL,
         "formato": "texto",            "descripcion": "Modelo LLM activo"},
        {"kpi": "vector_store",         "valor": config.VECTOR_STORE_PROVIDER,
         "formato": "texto",            "descripcion": "Backend de vector store"},
        {"kpi": "api_version",          "valor": config.API_VERSION,
         "formato": "texto",            "descripcion": "Versión de la API"},
        {"kpi": "langsmith_proyecto",   "valor": config.LANGSMITH_PROJECT if config.LANGSMITH_ENABLED else "desactivado",
         "formato": "texto",            "descripcion": "Proyecto LangSmith"},
        {"kpi": "tokens_totales",
         "valor": sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in registros),
         "formato": "numero",           "descripcion": "Total tokens consumidos"},
        {"kpi": "generado_en",          "valor": datetime.now().strftime("%Y-%m-%d %H:%M"),
         "formato": "fecha",            "descripcion": "Fecha de generación del reporte"},
    ]

    ruta = out_dir / "04_kpi_produccion.csv"
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["kpi", "valor", "formato", "descripcion"])
        writer.writeheader()
        writer.writerows(filas)

    return len(filas)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(n: int | None = None):
    out_dir = config.RESULTADOS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Cargar logs
    registros = _cargar_logs(n=n)
    es_ejemplo = False

    if not registros:
        print("\n  AVISO: No hay logs en logs/consultas.jsonl.")
        print("  Generando datos de ejemplo para demostración.\n")
        registros = _generar_datos_ejemplo()
        es_ejemplo = True
    else:
        print(f"\n  Cargados {len(registros)} registros de logs/consultas.jsonl\n")

    print(f"Exportando dashboard de producción en 'resultados/'...")
    print(f"  LLM      : {config.LLM_PROVIDER} / {config.LLM_MODEL}")
    print(f"  Backend  : {config.VECTOR_STORE_PROVIDER.upper()}")
    print()

    # Generar CSVs
    n1 = generar_01_consultas_log(registros, out_dir)
    n2 = generar_02_metricas_latencia(registros, out_dir)
    n3 = generar_03_analisis_costos(registros, out_dir)
    n4 = generar_04_kpi_produccion(registros, out_dir)

    # Resumen
    total_filas = n1 + n2 + n3 + n4

    print(f"  {'01_consultas_log.csv':<42} {n1:>4} filas  —  Log completo de consultas")
    print(f"  {'02_metricas_latencia.csv':<42} {n2:>4} filas  —  Percentiles de latencia (p25/p50/p95/p99)")
    print(f"  {'03_analisis_costos.csv':<42} {n3:>4} filas  —  Costo por proveedor y proyecciones")
    print(f"  {'04_kpi_produccion.csv':<42} {n4:>4} filas  —  KPIs para portada del dashboard")
    print()
    print(f"Total: {total_filas} filas en 4 archivos")
    print(f"Directorio: {out_dir}")

    if es_ejemplo:
        print()
        print(f"  NOTA: Datos de ejemplo. Para datos reales:")
        print(f"    1. uvicorn main:app --port 8001")
        print(f"    2. Haz consultas desde http://localhost:8001/ui o el endpoint /consulta")
        print(f"    3. python exportar_dashboard.py")

    print()
    print(f"Compatible con: Power BI · Tableau · Metabase · Looker Studio · Excel")
    if config.LANGSMITH_ENABLED:
        print(f"LangSmith: https://smith.langchain.com/projects")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Exportar métricas de producción a CSVs · agenteIA_TRM · USB Medellín"
    )
    parser.add_argument("--n", type=int, default=None,
                        help="Últimas N consultas a incluir (default: todas)")
    args = parser.parse_args()
    main(n=args.n)
