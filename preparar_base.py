"""
preparar_base.py — Ingesta de documentos DANE en pgvector
=========================================================
Proyecto agente_IA_TRM · USB Medellín

EJECUTAR UNA VEZ antes de iniciar la API:
    python preparar_base.py

Qué hace:
  1. Lee los 4 reportes .txt de la carpeta documentos/
  2. Divide cada documento en fragmentos solapados (chunking)
  3. Crea embeddings vectoriales con OpenAI text-embedding-3-small
  4. Guarda los vectores en pgvector (PostgreSQL)

Documentos incluidos en documentos/:
  - boletin_desempleo_2024.txt  → Mercado laboral Q3 2024
  - boletin_ipc_2024.txt        → IPC / inflación diciembre 2024
  - cuentas_nacionales_pib_2024.txt → PIB Colombia 2024
  - censo_poblacion_2023.txt    → Censo Nacional 2023

Requisito: pip install -r requirements.txt
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
from vectorstore_factory import crear_embeddings, crear_vectorstore


# ---------------------------------------------------------------------------
# Ingesta principal
# ---------------------------------------------------------------------------

def main():
    print(f"\n{'='*60}")
    print(f"  PREPARAR BASE VECTORIAL — agente_IA_TRM")
    print(f"  Backend: PGVECTOR")
    print(f"  Base de datos: {config.PG_DATABASE} en {config.PG_HOST}:{config.PG_PORT}")
    print(f"{'='*60}\n")

    # Verificar que existen los documentos
    if not config.DOCS_DIR.exists():
        print(f"ERROR: No se encontró la carpeta de documentos: {config.DOCS_DIR}")
        sys.exit(1)

    archivos = sorted(config.DOCS_DIR.glob("*.txt"))
    if not archivos:
        print(f"ERROR: No hay archivos .txt en {config.DOCS_DIR}")
        sys.exit(1)

    print(f"Documentos encontrados ({len(archivos)}):")
    for a in archivos:
        print(f"  - {a.name}  ({a.stat().st_size // 1024} KB)")
    print()

    # Paso 1: Cargar documentos
    from langchain_community.document_loaders import TextLoader

    docs = []
    for archivo in archivos:
        loader = TextLoader(str(archivo), encoding="utf-8")
        docs_cargados = loader.load()
        for d in docs_cargados:
            d.metadata["fuente"]  = archivo.stem
            d.metadata["titulo"]  = _titulo_legible(archivo.stem)
            d.metadata["archivo"] = archivo.name
        docs.extend(docs_cargados)
        print(f"  Cargado: {archivo.name}  ({len(docs_cargados[0].page_content)} chars)")

    print(f"\n  Total documentos cargados: {len(docs)}")

    # Paso 2: Dividir en fragmentos
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " "],
        length_function=len,
    )
    fragmentos = splitter.split_documents(docs)
    print(f"\n  Fragmentos generados: {len(fragmentos)}")
    print(f"  Configuración: chunk_size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP}")

    # Paso 3: Crear embeddings
    print(f"\n  Creando embeddings ({config.EMBEDDING_PROVIDER} / {config.EMBEDDING_MODEL})...")
    embeddings = crear_embeddings(config)

    # Paso 4: Guardar en pgvector
    print(f"\n  Guardando vectores en pgvector...")
    vectorstore = crear_vectorstore(fragmentos, embeddings, config)

    # Verificar que funciona
    print(f"\n  Verificando búsqueda semántica...")
    resultados = vectorstore.similarity_search("tasa de desempleo Colombia", k=2)
    print(f"  Test búsqueda 'desempleo' → {len(resultados)} fragmentos encontrados")
    if resultados:
        print(f"  Fragmento de muestra ({resultados[0].metadata.get('fuente', '')}):")
        print(f"  \"{resultados[0].page_content[:120]}...\"")

    print(f"\n{'='*60}")
    print(f"  BASE VECTORIAL LISTA")
    print(f"{'='*60}")
    print(f"  Backend     : PGVECTOR")
    print(f"  Base datos  : {config.PG_DATABASE}")
    print(f"  Colección   : {config.PG_COLLECTION}")
    print(f"  Documentos  : {len(docs)}")
    print(f"  Fragmentos  : {len(fragmentos)}")
    print(f"  Embeddings  : {config.EMBEDDING_PROVIDER} / {config.EMBEDDING_MODEL}")
    print(f"\n  Ahora puedes iniciar la API:")
    print(f"    python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload")
    print(f"{'='*60}\n")


def _titulo_legible(stem: str) -> str:
    """boletin_desempleo_2024 → Boletin Desempleo 2024"""
    return stem.replace("_", " ").title()


if __name__ == "__main__":
    main()
