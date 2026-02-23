"""
vectorstore_factory.py — Fábrica de Vector Store con pgvector
=============================================================
Proyecto agente_IA_TRM · USB Medellín

Backend soportado: pgvector (PostgreSQL + extensión vector)

Uso desde preparar_base.py (crear índice):
    from vectorstore_factory import crear_embeddings, crear_vectorstore
    emb = crear_embeddings(config)
    vs  = crear_vectorstore(fragmentos, emb, config)

Uso desde tools.py (cargar índice existente):
    from vectorstore_factory import crear_embeddings, cargar_vectorstore
    emb = crear_embeddings(config)
    vs  = cargar_vectorstore(emb, config)
    resultados = vs.similarity_search_with_score(query, k=k)
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ===========================================================================
# Embeddings — crea la instancia del modelo de embeddings
# ===========================================================================

def crear_embeddings(config):
    """
    Instancia el modelo de embeddings según config.EMBEDDING_PROVIDER.
    Por defecto: OpenAI text-embedding-3-small.
    """
    provider = config.EMBEDDING_PROVIDER
    model    = config.EMBEDDING_MODEL

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(model=model)
    else:  # openai (default)
        from langchain_openai import OpenAIEmbeddings
        api_key = config._API_KEYS.get("openai", "") or config.LLM_API_KEY
        return OpenAIEmbeddings(model=model, api_key=api_key)


# ===========================================================================
# Helpers internos
# ===========================================================================

def _pg_conn_str(config):
    """Construye la cadena de conexión para PostgreSQL."""
    host = getattr(config, "PG_HOST",     "localhost")
    port = getattr(config, "PG_PORT",     5432)
    db   = getattr(config, "PG_DATABASE", "bdvector")
    user = getattr(config, "PG_USER",     "postgres")
    pw   = getattr(config, "PG_PASSWORD", "")
    return f"postgresql+psycopg://{user}:{pw}@{host}:{port}/{db}"


# ===========================================================================
# crear_vectorstore — construye y persiste el índice desde documentos
# ===========================================================================

def crear_vectorstore(documentos, embeddings, config):
    """
    Crea un nuevo índice vectorial en pgvector con los documentos indicados.
    Si la colección ya existía, la borra y la recrea (pre_delete_collection=True).
    Retorna el vector store listo para búsqueda semántica.
    """
    try:
        from langchain_postgres import PGVector
    except ImportError:
        raise ImportError(
            "Paquete langchain-postgres no instalado.\n"
            "  pip install langchain-postgres 'psycopg[binary]'"
        )

    conn_str   = _pg_conn_str(config)
    collection = getattr(config, "PG_COLLECTION", "dane_reportes")

    print(f"[pgvector] Conectando a PostgreSQL...")
    vs = PGVector.from_documents(
        documents=documentos,
        embedding=embeddings,
        connection=conn_str,
        collection_name=collection,
        pre_delete_collection=True,
    )
    db = getattr(config, "PG_DATABASE", "bdvector")
    print(f"[pgvector] Colección '{collection}' guardada en base '{db}'")
    return vs


# ===========================================================================
# cargar_vectorstore — carga el índice ya creado
# ===========================================================================

def cargar_vectorstore(embeddings, config):
    """
    Carga el índice vectorial existente desde pgvector.
    Debe haberse ejecutado preparar_base.py al menos una vez.
    Retorna el vector store listo para similarity_search_with_score().
    """
    try:
        from langchain_postgres import PGVector
    except ImportError:
        raise ImportError(
            "pip install langchain-postgres 'psycopg[binary]'"
        )

    conn_str   = _pg_conn_str(config)
    collection = getattr(config, "PG_COLLECTION", "dane_reportes")
    return PGVector(
        embeddings=embeddings,
        connection=conn_str,
        collection_name=collection,
    )
