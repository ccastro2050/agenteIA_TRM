"""
config.py — Configuración del proyecto agente_IA_TRM
=====================================================
Agente de Analítica de Datos · USB Medellín

Proyecto 100% autónomo — no depende de ningún otro capítulo.
Incluye su propio agente ReAct, herramientas, documentos y vector store.

Vector store soportado: pgvector (PostgreSQL + extensión vector)
Base de datos operacional: SQLite (prompts, configuración, historial)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path)


# ---------------------------------------------------------------------------
# Directorios — todo dentro de agenteIA_TRM/
# ---------------------------------------------------------------------------

BASE_DIR       : Path = Path(__file__).parent
DATOS_DIR      : Path = BASE_DIR / "datos"
DOCS_DIR       : Path = BASE_DIR / "documentos"
LOGS_DIR       : Path = BASE_DIR / "logs"
RESULTADOS_DIR : Path = BASE_DIR / "resultados"
SQLITE_PATH    : Path = BASE_DIR / "agente_config.db"   # prompts + config UI


# ---------------------------------------------------------------------------
# Función helper
# ---------------------------------------------------------------------------

def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ---------------------------------------------------------------------------
# API REST — servidor FastAPI
# ---------------------------------------------------------------------------

API_TITLE   : str = "Agente IA Colombia — API de Analítica"
API_VERSION : str = "1.0.0"
API_DESC    : str = (
    "API REST para consultas a un agente de analítica económica colombiana. "
    "Responde preguntas sobre TRM, comercio exterior y estadísticas DANE."
)
HOST        : str = _get("HOST", "0.0.0.0")
PORT        : int = int(_get("PORT", "8001"))


# ---------------------------------------------------------------------------
# Proveedores LLM
# ---------------------------------------------------------------------------

_PROVIDER_BASE_URLS: dict[str, str] = {
    "anthropic": "",
    "openai":    "https://api.openai.com/v1",
    "ollama":    "http://localhost:11434/v1",
    "deepseek":  "https://api.deepseek.com/v1",
    "qwen":      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu":     "https://open.bigmodel.cn/api/paas/v4/",
    "moonshot":  "https://api.moonshot.cn/v1",
}

SUPPORTED_PROVIDERS = list(_PROVIDER_BASE_URLS.keys())

_API_KEYS: dict[str, str] = {
    "anthropic": _get("ANTHROPIC_API_KEY", "sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX-XXXXXXXX"),
    "openai":    _get("OPENAI_API_KEY",    "sk-proj-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"),
    "deepseek":  _get("DEEPSEEK_API_KEY",  "sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"),
    "ollama":    "ollama",
    "qwen":      _get("QWEN_API_KEY",      ""),
    "zhipu":     _get("ZHIPU_API_KEY",     ""),
    "moonshot":  _get("MOONSHOT_API_KEY",  ""),
}

LLM_PROVIDER: str = _get("LLM_PROVIDER", "deepseek").lower()
LLM_MODEL:    str = _get("LLM_MODEL",    "deepseek-chat")
LLM_API_KEY:  str = _API_KEYS.get(LLM_PROVIDER, "")
_custom_base  = _get("LLM_BASE_URL")
LLM_BASE_URL: str = _custom_base if _custom_base else _PROVIDER_BASE_URLS.get(LLM_PROVIDER, "")


# ---------------------------------------------------------------------------
# Costos por proveedor — USD por 1 000 tokens
# ---------------------------------------------------------------------------

# Precios aproximados (consultar precios actuales en cada proveedor)
COSTOS_POR_PROVEEDOR: dict[str, dict[str, float]] = {
    "anthropic": {"input": 0.003,    "output": 0.015},    # claude-sonnet-4-6
    "openai":    {"input": 0.00015,  "output": 0.0006},   # gpt-4o-mini
    "deepseek":  {"input": 0.00014,  "output": 0.00028},  # deepseek-chat
    "ollama":    {"input": 0.0,      "output": 0.0},      # local — sin costo
    "qwen":      {"input": 0.0005,   "output": 0.0015},   # qwen-turbo aprox.
    "zhipu":     {"input": 0.0007,   "output": 0.0007},   # glm-4-flash aprox.
    "moonshot":  {"input": 0.001,    "output": 0.003},    # moonshot-v1-8k aprox.
}


# ---------------------------------------------------------------------------
# LangSmith — observabilidad
# ---------------------------------------------------------------------------

LANGSMITH_API_KEY : str  = _get("LANGSMITH_API_KEY",  "lsv2_pt_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX_XXXXXXXXXXXXXXXX")
LANGSMITH_PROJECT : str  = _get("LANGSMITH_PROJECT",  "agenteIA-TRM")
LANGSMITH_ENABLED : bool = bool(LANGSMITH_API_KEY)


# ---------------------------------------------------------------------------
# Embeddings — para el vector store
# ---------------------------------------------------------------------------

_EMBEDDING_DEFAULTS: dict[str, str] = {
    "openai":      "text-embedding-3-small",
    "ollama":      "nomic-embed-text",
    "huggingface": "paraphrase-multilingual-MiniLM-L12-v2",
}
EMBEDDING_PROVIDER: str = _get("EMBEDDING_PROVIDER", "openai").lower()
EMBEDDING_MODEL:    str = _get(
    "EMBEDDING_MODEL",
    _EMBEDDING_DEFAULTS.get(EMBEDDING_PROVIDER, "text-embedding-3-small"),
)

# RAG — fragmentos a recuperar por búsqueda
RETRIEVAL_K: int = int(_get("RETRIEVAL_K", "4"))

# Chunking (preparar_base.py)
CHUNK_SIZE:    int = int(_get("CHUNK_SIZE",    "800"))
CHUNK_OVERLAP: int = int(_get("CHUNK_OVERLAP", "100"))


# ---------------------------------------------------------------------------
# Vector Store — pgvector (único backend soportado)
# ---------------------------------------------------------------------------

VECTOR_STORE_PROVIDER: str = "pgvector"

# pgvector (PostgreSQL + extensión vector)
PG_HOST:       str = _get("PG_HOST",       "localhost")
PG_PORT:       int = int(_get("PG_PORT",   "5432"))
PG_DATABASE:   str = _get("PG_DATABASE",   "bdvector")
PG_USER:       str = _get("PG_USER",       "postgres")
PG_PASSWORD:   str = _get("PG_PASSWORD",   "postgres")
PG_COLLECTION: str = _get("PG_COLLECTION", "dane_reportes")


# ---------------------------------------------------------------------------
# Modelos disponibles por proveedor (para la UI)
# ---------------------------------------------------------------------------

MODELOS_POR_PROVEEDOR: dict[str, list[str]] = {
    "anthropic": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "deepseek":  ["deepseek-chat", "deepseek-reasoner"],
    "ollama":    ["llama3.2", "mistral", "llama3.1", "qwen2.5"],
    "qwen":      ["qwen-turbo", "qwen-plus", "qwen-max"],
    "zhipu":     ["glm-4-flash", "glm-4-air", "glm-4"],
    "moonshot":  ["moonshot-v1-8k", "moonshot-v1-32k"],
}


# ---------------------------------------------------------------------------
# Crear LLM
# ---------------------------------------------------------------------------

def _make_llm(provider: str, model: str, api_key: str, base_url: str,
              temperature: float = 0.2, max_tokens: int = 2048):
    """Fábrica común de LLMs — mismo patrón que caps 1-7."""
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key,
                             temperature=temperature, max_tokens=max_tokens)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, base_url="http://localhost:11434")
    else:
        from langchain_openai import ChatOpenAI
        kwargs: dict = {"model": model, "api_key": api_key,
                        "temperature": temperature, "max_tokens": max_tokens}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)


def crear_llm(temperature: float = 0.2):
    """LLM según configuración del .env."""
    return _make_llm(LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BASE_URL,
                     temperature=temperature)


def crear_llm_dinamico(temperature: float = 0.2):
    """
    LLM que lee proveedor/modelo/api_key desde SQLite (UI) primero.
    Si no hay nada en SQLite, cae de vuelta a los valores del .env.

    Permite cambiar el modelo desde la interfaz web sin reiniciar la API.
    """
    try:
        import database
        db_cfg   = database.get_all_config()
        provider = db_cfg.get("llm_provider", "") or LLM_PROVIDER
        model    = db_cfg.get("llm_model",    "") or LLM_MODEL
        api_key  = db_cfg.get("llm_api_key",  "") or _API_KEYS.get(provider, LLM_API_KEY)
    except Exception:
        provider = LLM_PROVIDER
        model    = LLM_MODEL
        api_key  = LLM_API_KEY

    base_url = _PROVIDER_BASE_URLS.get(provider, "")
    return _make_llm(provider, model, api_key, base_url, temperature=temperature)


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

def validate():
    if LLM_PROVIDER not in SUPPORTED_PROVIDERS:
        raise EnvironmentError(
            f"[CONFIG] Proveedor LLM no reconocido: '{LLM_PROVIDER}'\n"
            f"  Soportados: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    if not DATOS_DIR.exists():
        raise EnvironmentError(
            f"[CONFIG] Directorio de datos no encontrado: {DATOS_DIR}\n"
            f"  La carpeta 'datos/' debe existir con los CSV del proyecto."
        )
    if not DOCS_DIR.exists():
        raise EnvironmentError(
            f"[CONFIG] Directorio de documentos no encontrado: {DOCS_DIR}\n"
            f"  La carpeta 'documentos/' debe existir con los .txt del DANE."
        )

    print(f"[CONFIG] LLM              : {LLM_PROVIDER} / {LLM_MODEL}")
    print(f"[CONFIG] Embeddings       : {EMBEDDING_PROVIDER} / {EMBEDDING_MODEL}")
    print(f"[CONFIG] Vector store     : {VECTOR_STORE_PROVIDER.upper()}")
    print(f"[CONFIG] Base de datos    : {PG_DATABASE} en {PG_HOST}:{PG_PORT}")
    print(f"[CONFIG] API              : {HOST}:{PORT}  v{API_VERSION}")
    print(f"[CONFIG] LangSmith        : {'habilitado' if LANGSMITH_ENABLED else 'deshabilitado'}")
    if LANGSMITH_ENABLED:
        print(f"[CONFIG]   Proyecto       : {LANGSMITH_PROJECT}")

    csvs = list(DATOS_DIR.glob("*.csv"))
    txts = list(DOCS_DIR.glob("*.txt"))
    print(f"[CONFIG] Datasets CSV     : {len(csvs)} archivos en datos/")
    print(f"[CONFIG] Documentos TXT   : {len(txts)} archivos en documentos/")
    print()
