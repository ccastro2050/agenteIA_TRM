"""
database.py — Persistencia SQLite para prompts y configuración
==============================================================
Proyecto agente_IA_TRM · USB Medellín

Responsabilidades:
  1. Almacenar los 6 prompts de los agentes (editables desde la UI)
  2. Guardar la configuración de la UI (proveedor, modelo, api_key)
  3. Registrar el historial de consultas con métricas (latencia, tokens, costo)
  4. Proveer funciones de lectura y escritura para main.py y los agentes

SQLite es la base de datos operacional del proyecto.
pgvector es el índice vectorial para búsqueda semántica.
Son complementarios: SQLite guarda configuración, pgvector guarda vectores.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH: Path = Path(__file__).parent / "agente_config.db"


# ---------------------------------------------------------------------------
# Prompts por defecto (igual a los hardcodeados en los agentes)
# ---------------------------------------------------------------------------

PROMPTS_DEFAULT: dict[str, str] = {

    "langchain_main": (
        "Eres un analista económico de Colombia con acceso a tres dominios de información:\n\n"
        "1. TIPO DE CAMBIO (TRM)\n"
        "   - obtener_trm_actual()          → TRM vigente en diciembre 2024 y variación mensual\n"
        "   - analizar_historico_trm(meses) → tendencia del dólar en los últimos N meses\n\n"
        "2. COMERCIO EXTERIOR\n"
        "   - consultar_balanza_comercial()       → exportaciones vs importaciones mensuales 2024\n"
        "   - analizar_sectores_exportacion()     → sectores exportadores y su participación\n\n"
        "3. DOCUMENTOS DANE (requiere índice vectorial — ejecutar preparar_base.py)\n"
        "   - listar_reportes_dane()              → catálogo de reportes disponibles\n"
        "   - buscar_documentos_dane(query, k)    → búsqueda semántica en reportes de desempleo,\n"
        "                                           inflación, PIB y censo de población\n\n"
        "INSTRUCCIONES:\n"
        "- Identifica qué dominio(s) necesitas para responder la pregunta.\n"
        "- Si la pregunta involucra múltiples temas, usa herramientas de varios dominios.\n"
        "- Llama primero a las herramientas de catálogo (listar_*) cuando no estés seguro.\n"
        "- Cita siempre los números exactos de las herramientas (no inventes cifras).\n"
        "- Responde SIEMPRE en español con una conclusión clara al final.\n"
        "- Para preguntas cruzadas (ej: TRM + inflación), explica la relación entre ambas."
    ),

    "langgraph_supervisor": (
        "Eres un enrutador de consultas económicas. Clasifica la pregunta en UNA de estas rutas:\n\n"
        "  'trm'      → solo sobre tipo de cambio: dólar, TRM, devaluación, variación del peso\n"
        "  'datos'    → solo sobre comercio exterior: exportaciones, importaciones, balanza, sectores\n"
        "  'rag'      → solo sobre estadísticas DANE: desempleo, inflación, PIB, población, censo\n"
        "  'multiple' → combina TRM+DANE, o TRM+exportaciones con contexto macro\n\n"
        "Responde EXACTAMENTE con este JSON (sin markdown):\n"
        "{\"ruta\": \"<ruta>\", \"justificacion\": \"<una oración breve>\"}"
    ),

    "langgraph_trm": (
        "Eres un analista de mercado cambiario especializado en el peso colombiano. "
        "Responde preguntas sobre el TRM (tipo de cambio dolar/peso) usando las herramientas disponibles. "
        "Siempre menciona el valor exacto del TRM, la tendencia y una interpretacion economica breve. "
        "Responde en español, conciso y con datos precisos."
    ),

    "langgraph_datos": (
        "Eres un analista de comercio exterior de Colombia. "
        "Responde preguntas sobre exportaciones, importaciones y balanza comercial del 2024. "
        "Destaca los sectores mas importantes, el deficit/superavit y tendencias clave. "
        "Usa datos exactos de las herramientas. Responde en español."
    ),

    "langgraph_rag": (
        "Eres un investigador especializado en estadisticas del DANE Colombia. "
        "Responde preguntas buscando en los reportes disponibles: desempleo, IPC, PIB y censo. "
        "Llama primero a listar_reportes_dane() para conocer las fuentes, luego "
        "buscar_documentos_dane() con terminos relevantes para encontrar la informacion. "
        "Cita los documentos fuente y los valores exactos encontrados. Responde en español."
    ),

    "langgraph_sintetizador": (
        "Eres un analista económico que integra información de múltiples fuentes. "
        "Recibes respuestas de agentes especializados y debes sintetizarlas en "
        "una respuesta única, coherente y bien estructurada en español. "
        "Organiza la respuesta con secciones claras si hay múltiples temas. "
        "Incluye una conclusión que relacione los diferentes aspectos si aplica. "
        "Cita los números exactos mencionados por los agentes."
    ),
}


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Crea las tablas SQLite si no existen e inserta los prompts por defecto.
    Seguro de llamar múltiples veces (idempotente).
    """
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            nombre     TEXT PRIMARY KEY,
            contenido  TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave      TEXT PRIMARY KEY,
            valor      TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS consultas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            pregunta    TEXT    NOT NULL,
            respuesta   TEXT    NOT NULL,
            latencia_ms REAL    DEFAULT 0,
            tokens_in   INTEGER DEFAULT 0,
            tokens_out  INTEGER DEFAULT 0,
            costo_usd   REAL    DEFAULT 0,
            modelo      TEXT    DEFAULT '',
            backend     TEXT    DEFAULT 'langgraph'
        )
    """)

    # Insertar defaults solo si no existen (INSERT OR IGNORE)
    for nombre, contenido in PROMPTS_DEFAULT.items():
        c.execute(
            "INSERT OR IGNORE INTO prompts (nombre, contenido) VALUES (?, ?)",
            (nombre, contenido),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def get_prompt(nombre: str) -> str:
    """Retorna el contenido del prompt. Si no existe, retorna el default."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT contenido FROM prompts WHERE nombre = ?", (nombre,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else PROMPTS_DEFAULT.get(nombre, "")


def save_prompt(nombre: str, contenido: str) -> None:
    """Guarda o actualiza un prompt en SQLite."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO prompts (nombre, contenido, updated_at)
        VALUES (?, ?, datetime('now'))
    """, (nombre, contenido))
    conn.commit()
    conn.close()


def get_all_prompts() -> dict[str, str]:
    """Retorna todos los prompts. Combina SQLite con defaults (SQLite tiene prioridad)."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT nombre, contenido FROM prompts")
    rows = c.fetchall()
    conn.close()
    resultado = dict(PROMPTS_DEFAULT)              # base = defaults
    resultado.update({r[0]: r[1] for r in rows})  # SQLite sobreescribe
    return resultado


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def get_config(clave: str, default: str = "") -> str:
    """Retorna el valor de una clave de configuración."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def save_config(clave: str, valor: str) -> None:
    """Guarda o actualiza una clave de configuración."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO configuracion (clave, valor, updated_at)
        VALUES (?, ?, datetime('now'))
    """, (clave, str(valor)))
    conn.commit()
    conn.close()


def get_all_config() -> dict[str, str]:
    """Retorna toda la configuración guardada en SQLite."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT clave, valor FROM configuracion")
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# Historial de consultas
# ---------------------------------------------------------------------------

def save_consulta(
    timestamp:   str,
    pregunta:    str,
    respuesta:   str,
    latencia_ms: float,
    tokens_in:   int,
    tokens_out:  int,
    costo_usd:   float,
    modelo:      str,
    backend:     str = "langgraph",
) -> None:
    """Guarda una consulta en la tabla SQLite consultas."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        INSERT INTO consultas
            (timestamp, pregunta, respuesta, latencia_ms,
             tokens_in, tokens_out, costo_usd, modelo, backend)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, pregunta, respuesta, latencia_ms,
          tokens_in, tokens_out, costo_usd, modelo, backend))
    conn.commit()
    conn.close()


def get_historial(n: int = 10) -> list[dict]:
    """Retorna las últimas n consultas ordenadas de más reciente a más antigua."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("""
        SELECT timestamp, pregunta, respuesta, latencia_ms,
               tokens_in, tokens_out, costo_usd, modelo, backend
        FROM consultas
        ORDER BY id DESC
        LIMIT ?
    """, (n,))
    rows = c.fetchall()
    conn.close()
    cols = ["timestamp", "pregunta", "respuesta", "latencia_ms",
            "tokens_in", "tokens_out", "costo_usd", "modelo", "backend"]
    return [dict(zip(cols, r)) for r in rows]


def get_metricas_consultas() -> dict:
    """Calcula métricas operativas desde SQLite."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM consultas")
    total = c.fetchone()[0]
    if total == 0:
        conn.close()
        return {"sin_datos": True,
                "mensaje": "No hay consultas registradas aún."}

    c.execute("""
        SELECT
            AVG(latencia_ms), MIN(latencia_ms), MAX(latencia_ms),
            SUM(tokens_in),   SUM(tokens_out),
            SUM(costo_usd),   AVG(costo_usd),
            MIN(timestamp),   MAX(timestamp)
        FROM consultas
    """)
    row = c.fetchone()

    c.execute("SELECT latencia_ms FROM consultas ORDER BY latencia_ms")
    lats = [r[0] for r in c.fetchall()]

    c.execute("SELECT modelo, COUNT(*) FROM consultas GROUP BY modelo")
    por_modelo = {r[0]: r[1] for r in c.fetchall()}

    conn.close()

    def pct(lst, p):
        return round(lst[max(0, int(len(lst) * p / 100) - 1)], 1)

    total_in, total_out = int(row[3] or 0), int(row[4] or 0)
    costo_tot = round(float(row[5] or 0), 4)

    return {
        "total_consultas":      total,
        "latencia_promedio_ms": round(float(row[0] or 0), 1),
        "latencia_min_ms":      round(float(row[1] or 0), 1),
        "latencia_max_ms":      round(float(row[2] or 0), 1),
        "latencia_p50_ms":      pct(lats, 50),
        "latencia_p95_ms":      pct(lats, 95),
        "latencia_p99_ms":      pct(lats, 99),
        "tokens_in_total":      total_in,
        "tokens_out_total":     total_out,
        "tokens_total":         total_in + total_out,
        "costo_total_usd":      costo_tot,
        "costo_promedio_usd":   round(float(row[6] or 0), 6),
        "costo_por_mil_tokens": round(costo_tot / max(total_in + total_out, 1) * 1000, 4),
        "consultas_por_modelo": por_modelo,
        "primera_consulta":     row[7],
        "ultima_consulta":      row[8],
    }


# ---------------------------------------------------------------------------
# Punto de entrada (diagnóstico)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print(f"SQLite: {DB_PATH}")
    print(f"Prompts: {list(get_all_prompts().keys())}")
    print(f"Config: {get_all_config()}")
    print("OK — base de datos inicializada")
