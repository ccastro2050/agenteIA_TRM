# Documento 04 — Preparación de Datos

**Proyecto:** agente_IA_TRM
**Serie:** Tutorial de construcción paso a paso
**Prerequisito:** Documento 03 — Configuración del Entorno
**Repositorio:** https://github.com/ccastro2050/agenteIA_TRM

---

## 1. Dos tipos de datos en el proyecto

El agente trabaja con dos tipos de información complementarios:

| Tipo | Formato | Carpeta | Uso |
|------|---------|---------|-----|
| **Estructurado** | CSV | `datos/` | Herramientas de consulta directa (TRM, comercio) |
| **No estructurado** | TXT | `documentos/` | Búsqueda semántica con RAG y pgvector |

Los archivos CSV se consultan con pandas (lectura de tablas).
Los archivos TXT se convierten en vectores y se almacenan en pgvector
para responder preguntas en lenguaje natural sobre su contenido.

---

## 2. Archivos CSV — datos estructurados

Los CSV viven en la carpeta `datos/` y contienen estadísticas económicas
de Colombia para el año 2024.

### `trm_2024.csv`

Tasa Representativa del Mercado (TRM) mensual — precio del dólar en pesos:

```
año,mes,nombre_mes,trm,variacion_pct
2024,1,Enero,3847.35,0.00
2024,2,Febrero,3969.70,3.18
2024,3,Marzo,3976.15,0.16
...
2024,12,Diciembre,4359.00,2.45
```

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `año` | int | Año (2024) |
| `mes` | int | Número de mes (1-12) |
| `nombre_mes` | str | Nombre del mes en español |
| `trm` | float | Pesos colombianos por 1 USD |
| `variacion_pct` | float | Variación porcentual respecto al mes anterior |

### `comercio_exterior_2024.csv`

Exportaciones e importaciones mensuales de Colombia en millones de USD:

```
año,mes,nombre_mes,exportaciones_usd_mill,importaciones_usd_mill,balanza_comercial
2024,1,Enero,3892.4,5487.1,-1594.7
2024,2,Febrero,4125.8,5628.3,-1502.5
...
```

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `exportaciones_usd_mill` | float | Exportaciones en millones de USD |
| `importaciones_usd_mill` | float | Importaciones en millones de USD |
| `balanza_comercial` | float | Diferencia (negativo = déficit) |

### `exportaciones_sectores_2024.csv`

Exportaciones anuales 2024 por sector económico:

```
sector,valor_usd_mill,participacion_pct,variacion_anual_pct
Petróleo y derivados,20847.3,40.2,-3.1
Carbón,9325.6,17.9,1.8
Café,4523.1,8.7,5.2
...
```

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `sector` | str | Nombre del sector exportador |
| `valor_usd_mill` | float | Valor en millones de USD |
| `participacion_pct` | float | Porcentaje del total exportado |
| `variacion_anual_pct` | float | Crecimiento respecto al año anterior |

---

## 3. Archivos TXT — documentos para RAG

Los archivos de texto viven en la carpeta `documentos/` y son reportes
del DANE (Departamento Administrativo Nacional de Estadística) de Colombia.
Estos documentos **no se consultan directamente**: se convierten en vectores
y se guardan en pgvector para que el agente pueda buscar información
relevante en ellos con búsqueda semántica.

| Archivo | Contenido | Período |
|---------|-----------|---------|
| `boletin_desempleo_2024.txt` | Tasa de desempleo, mercado laboral, ciudades | Q3 2024 |
| `boletin_ipc_2024.txt` | Inflación, IPC, precios al consumidor | Diciembre 2024 |
| `cuentas_nacionales_pib_2024.txt` | PIB por sectores, crecimiento económico | 2024 |
| `censo_poblacion_2023.txt` | Población por departamento, demografía | 2023 |

### ¿Por qué TXT y no PDF?

Los archivos `.txt` (texto plano) son más simples de procesar que los PDF:
no requieren librerías de extracción de texto y garantizan que el contenido
sea legible sin pérdidas de formato. En proyectos reales, los PDF se
convierten a texto plano con herramientas como `pdfplumber` o `PyMuPDF`
antes de indexarlos.

---

## 4. `config.py` — la configuración central

El archivo `config.py` es el punto único de configuración del proyecto.
Lee todas las variables desde el archivo `.env` y las expone como
constantes Python.

### Por qué no hardcodear las claves en `config.py`

En un proyecto público en GitHub, `config.py` es visible para todos.
Si se escriben las claves directamente en el código, quedan expuestas.
La solución es leer los valores del `.env` con `python-dotenv`:

```python
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")   # "" si no existe
```

El archivo `.env` se agrega al `.gitignore` y **nunca se sube a GitHub**.

### Variables principales de `config.py`

```python
# ── Rutas de carpetas ──────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent          # carpeta raíz del proyecto
DATOS_DIR      = BASE_DIR / "datos"             # archivos CSV
DOCS_DIR       = BASE_DIR / "documentos"        # archivos TXT para RAG
LOGS_DIR       = BASE_DIR / "logs"              # logs de consultas
SQLITE_PATH    = BASE_DIR / "agente_config.db"  # SQLite: prompts + config UI

# ── Proveedor y modelo LLM (leídos del .env) ──────────────────────────
LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL      = os.getenv("LLM_MODEL",    "gpt-4o-mini")
LLM_API_KEY    = os.getenv("OPENAI_API_KEY", "")

# ── Embeddings ────────────────────────────────────────────────────────
EMBEDDING_PROVIDER = "openai"
EMBEDDING_MODEL    = "text-embedding-3-small"

# ── pgvector (PostgreSQL) ──────────────────────────────────────────────
PG_HOST       = os.getenv("PG_HOST",     "localhost")
PG_PORT       = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE   = os.getenv("PG_DATABASE", "bdvector")
PG_USER       = os.getenv("PG_USER",     "postgres")
PG_PASSWORD   = os.getenv("PG_PASSWORD", "")
PG_COLLECTION = os.getenv("PG_COLLECTION", "dane_reportes")

# ── Chunking (para preparar_base.py) ──────────────────────────────────
CHUNK_SIZE    = 800    # caracteres por fragmento
CHUNK_OVERLAP = 100    # solapamiento entre fragmentos consecutivos
RETRIEVAL_K   = 4      # fragmentos a recuperar en cada búsqueda RAG
```

### `crear_llm()` y `crear_llm_dinamico()`

`config.py` también expone dos funciones para crear el LLM:

- **`crear_llm()`**: usa los valores fijos del `.env`. Siempre retorna
  el mismo modelo.

- **`crear_llm_dinamico()`**: primero intenta leer el proveedor y modelo
  desde la base de datos SQLite (donde la interfaz web guarda los cambios).
  Si no hay nada en SQLite, cae de vuelta al `.env`. Esto permite cambiar
  el modelo desde la UI sin reiniciar el servidor.

---

## 5. `vectorstore_factory.py` — conexión con pgvector

Este archivo tiene dos responsabilidades:

1. **Crear embeddings**: instancia el modelo que convierte texto en vectores.
2. **Conectar con pgvector**: crea o carga el índice vectorial.

### `crear_embeddings(config)`

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=config._API_KEYS["openai"]
)
```

El resultado es un objeto que transforma cualquier texto en un vector
de 1 536 dimensiones (para `text-embedding-3-small`).

### `crear_vectorstore(documentos, embeddings, config)`

Crea la colección en pgvector borrando la anterior si existe:

```python
from langchain_postgres import PGVector

vs = PGVector.from_documents(
    documents=fragmentos,
    embedding=embeddings,
    connection="postgresql+psycopg://usuario:contraseña@localhost:5432/bdvector",
    collection_name="dane_reportes",
    pre_delete_collection=True,   # ← borra y recrea
)
```

### `cargar_vectorstore(embeddings, config)`

Carga la colección ya existente para hacer búsquedas:

```python
vs = PGVector(
    embeddings=embeddings,
    connection="postgresql+psycopg://...",
    collection_name="dane_reportes",
)

# Buscar fragmentos relevantes
resultados = vs.similarity_search_with_score("inflación diciembre", k=4)
```

---

## 6. `preparar_base.py` — el script de ingesta

Este script coordina los pasos 1 a 4 de la ingesta:

```
Paso 1: Leer archivos .txt de documentos/
Paso 2: Dividir en fragmentos (chunking)
Paso 3: Calcular embeddings (llamada a la API de OpenAI)
Paso 4: Guardar vectores en pgvector
```

### Paso 1 — Cargar documentos

`TextLoader` de LangChain lee el archivo `.txt` y lo convierte en un
objeto `Document` con el texto y metadatos:

```python
from langchain_community.document_loaders import TextLoader

loader = TextLoader("documentos/boletin_desempleo_2024.txt", encoding="utf-8")
docs   = loader.load()
# docs[0].page_content = "Boletín Técnico — Mercado Laboral..."
# docs[0].metadata     = {"source": "documentos/boletin_desempleo_2024.txt"}
```

El script agrega metadatos adicionales a cada documento:

```python
doc.metadata["fuente"]  = "boletin_desempleo_2024"   # nombre del archivo
doc.metadata["titulo"]  = "Boletin Desempleo 2024"   # título legible
doc.metadata["archivo"] = "boletin_desempleo_2024.txt"
```

Estos metadatos viajan con cada fragmento y permiten al agente citar
la fuente de la información.

### Paso 2 — Chunking (fragmentar documentos)

Un documento largo no cabe en el contexto de un embedding.
`RecursiveCharacterTextSplitter` lo divide en fragmentos de tamaño
controlado con solapamiento:

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,      # máximo 800 caracteres por fragmento
    chunk_overlap=100,   # los últimos 100 chars del fragmento N
                         # son los primeros del fragmento N+1
    separators=["\n\n", "\n", ". ", " "],
)
fragmentos = splitter.split_documents(docs)
```

**¿Por qué solapar?** Si una idea importante está en la frontera entre
dos fragmentos, el solapamiento garantiza que aparece completa en al
menos uno de los dos.

```
Fragmento 1: "...la tasa de desempleo en el tercer trimestre de 2024"
Fragmento 2: "trimestre de 2024 fue del 9.3%, lo que representa..."
                    ↑ solapamiento de 100 chars
```

### Paso 3 — Calcular embeddings

```python
embeddings = crear_embeddings(config)
# Internamente llama a la API de OpenAI con todos los fragmentos
# Cada fragmento → vector de 1 536 números (float32)
```

Esta es la única operación que consume créditos de la API de OpenAI.
Para los 4 documentos del proyecto (~163 fragmentos × ~200 tokens = ~32 600 tokens),
el costo es de aproximadamente **$0.001 USD** con `text-embedding-3-small`.

### Paso 4 — Guardar en pgvector

```python
vectorstore = crear_vectorstore(fragmentos, embeddings, config)
```

Internamente llama a `PGVector.from_documents()` que:
1. Crea la tabla `langchain_pg_embedding` en PostgreSQL si no existe
2. Inserta cada fragmento con su vector y metadatos

### Ejecutar el script

Con el entorno virtual activo y el `.env` configurado:

```bash
python preparar_base.py
```

Salida esperada:

```
============================================================
  PREPARAR BASE VECTORIAL — agente_IA_TRM
  Backend: PGVECTOR
  Base de datos: bdvector en localhost:5432
============================================================

Documentos encontrados (4):
  - boletin_desempleo_2024.txt  (18 KB)
  - boletin_ipc_2024.txt        (15 KB)
  - censo_poblacion_2023.txt    (21 KB)
  - cuentas_nacionales_pib_2024.txt  (17 KB)

  Cargado: boletin_desempleo_2024.txt  (18432 chars)
  Cargado: boletin_ipc_2024.txt        (15280 chars)
  Cargado: censo_poblacion_2023.txt    (21504 chars)
  Cargado: cuentas_nacionales_pib_2024.txt  (17920 chars)

  Total documentos cargados: 4

  Fragmentos generados: 163
  Configuración: chunk_size=800, overlap=100

  Creando embeddings (openai / text-embedding-3-small)...

  Guardando vectores en pgvector...
[pgvector] Conectando a PostgreSQL...
[pgvector] Colección 'dane_reportes' guardada en base 'bdvector'

  Verificando búsqueda semántica...
  Test búsqueda 'desempleo' → 2 fragmentos encontrados
  Fragmento de muestra (boletin_desempleo_2024):
  "La tasa global de participación fue de 62.7%..."

============================================================
  BASE VECTORIAL LISTA
============================================================
  Backend     : PGVECTOR
  Base datos  : bdvector
  Colección   : dane_reportes
  Documentos  : 4
  Fragmentos  : 163
  Embeddings  : openai / text-embedding-3-small

  Ahora puedes iniciar la API:
    python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
============================================================
```

---

## 7. Verificar los vectores en PostgreSQL

Para confirmar que los datos quedaron bien guardados, conectarse a
PostgreSQL y ejecutar:

```bash
psql -U postgres -d bdvector
```

Dentro de psql:

```sql
-- Ver las tablas creadas por pgvector / LangChain
\dt

-- Contar fragmentos guardados
SELECT COUNT(*) FROM langchain_pg_embedding;
-- Debe mostrar: 163 (aproximadamente)

-- Ver los metadatos de los primeros 3 fragmentos
SELECT
    cmetadata->>'fuente'  AS fuente,
    cmetadata->>'titulo'  AS titulo,
    LEFT(document, 80)    AS inicio_texto
FROM langchain_pg_embedding
LIMIT 3;

-- Salir
\q
```

---

## 8. ¿Cuándo volver a ejecutar `preparar_base.py`?

El script solo necesita ejecutarse:

1. **La primera vez**, antes de iniciar el servidor.
2. **Cada vez que se agregan o modifican documentos** en la carpeta
   `documentos/`. El script borra y recrea la colección completa
   (`pre_delete_collection=True`).

No es necesario ejecutarlo si solo se cambia el LLM, el proveedor o
cualquier otra configuración. Los vectores solo dependen del contenido
de los documentos.

---

## 9. Solución de problemas

### Error: `connection refused` (port 5432)
PostgreSQL no está corriendo. Iniciarlo:
```bash
net start postgresql-x64-15
# (ajustar el número de versión si es necesario)
```

### Error: `password authentication failed`
La contraseña en `.env` (`PG_PASSWORD`) no coincide con la configurada
en PostgreSQL. Verificar el valor y que la variable esté bien asignada.

### Error: `database "bdvector" does not exist`
La base de datos no se creó. Ejecutar los pasos del Documento 03,
sección 7 (Crear la base de datos en PostgreSQL).

### Error: `No module named 'langchain_postgres'`
Las dependencias no están instaladas o el entorno virtual no está activo:
```bash
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Error: `openai.AuthenticationError`
La clave `OPENAI_API_KEY` en el `.env` es incorrecta o vacía.
Los embeddings requieren siempre una clave de OpenAI válida,
independientemente del LLM que se use para las respuestas.

---

## Referencias

1. LangChain — TextLoader.
   https://python.langchain.com/docs/integrations/document_loaders/file_directory/

2. LangChain — RecursiveCharacterTextSplitter.
   https://python.langchain.com/docs/how_to/recursive_text_splitter/

3. LangChain — PGVector.
   https://python.langchain.com/docs/integrations/vectorstores/pgvector/

4. OpenAI Embeddings — text-embedding-3-small.
   https://platform.openai.com/docs/guides/embeddings

5. PostgreSQL — Documentación oficial.
   https://www.postgresql.org/docs/

6. pgvector — Open-source vector similarity search for Postgres.
   https://github.com/pgvector/pgvector

---

## Pasos Git

```bash
git add datos/ documentos/ requirements.txt config.py vectorstore_factory.py preparar_base.py tutorial_AgenteIA/04_preparacion_datos.md
git commit -m "feat: agrega datos, config, vectorstore y documento 04"
git push origin main
```

> **Siguiente documento:** `05_herramientas.md` — Las 6 herramientas del
> agente (`@tool`): cómo consultan los CSV con pandas, cómo realizan
> la búsqueda semántica en pgvector, y cómo se conectan al agente.
