# Documento 03 — Configuración del Entorno

**Proyecto:** agente_IA_TRM
**Serie:** Tutorial de construcción paso a paso
**Prerequisito:** Documento 02 — Arquitectura del Sistema
**Repositorio:** https://github.com/ccastro2050/agenteIA_TRM

---

## 1. Requisitos previos

Antes de empezar, verificar que el sistema tiene instalado:

| Requisito | Versión mínima | Cómo verificar |
|-----------|---------------|----------------|
| Python | 3.11 | `python --version` |
| Git | cualquier | `git --version` |
| PostgreSQL con pgvector | 15+ | Ver Documento 00 |

> **pgvector:** La instalación de PostgreSQL con la extensión pgvector
> en Windows está cubierta completamente en el
> **Documento 00 — Instalación pgvector en Windows**
> que se encuentra en esta misma carpeta `tutorial_AgenteIA/`.
> Completar ese documento antes de continuar.

---

## 2. Clonar el repositorio

Abrir una terminal (PowerShell, CMD o Git Bash) y ejecutar:

```bash
git clone https://github.com/ccastro2050/agenteIA_TRM.git
cd agenteIA_TRM
```

Verificar que la clonación fue exitosa:

```bash
# Debe mostrar la lista de archivos del proyecto
ls
```

---

## 3. Crear el entorno virtual de Python

Un **entorno virtual** es una instalación de Python aislada para este
proyecto. Permite instalar las dependencias necesarias sin afectar
otros proyectos ni el Python del sistema.

```bash
# Crear el entorno virtual en la carpeta .venv
python -m venv .venv
```

Activar el entorno virtual:

```bash
# Windows — PowerShell
.venv\Scripts\Activate.ps1

# Windows — CMD
.venv\Scripts\activate.bat

# Mac / Linux
source .venv/bin/activate
```

Cuando el entorno está activo, el prompt de la terminal muestra
`(.venv)` al inicio:

```
(.venv) C:\Users\usuario\agenteIA_TRM>
```

> **Importante:** el entorno virtual debe estar activo cada vez que
> se trabaje con el proyecto. Si se cierra la terminal, hay que
> activarlo de nuevo.

---

## 4. Instalar las dependencias

Con el entorno virtual activo, instalar todas las librerías del proyecto:

```bash
pip install -r requirements.txt
```

Este comando lee el archivo `requirements.txt` e instala exactamente
las versiones indicadas. La instalación tarda entre 2 y 5 minutos
según la velocidad de internet.

### ¿Qué contiene `requirements.txt`?

```
# LangChain y LangGraph
langchain>=1.2.10
langchain-core>=1.2.14
langchain-community>=0.4.1
langchain-text-splitters>=1.1.1
langgraph>=1.0.9

# Proveedores LLM
langchain-anthropic>=1.3.3
langchain-openai>=1.1.10

# API REST
fastapi>=0.129.0
uvicorn[standard]>=0.41.0
pydantic>=2.12.5
python-multipart>=0.0.22
jinja2>=3.1.6

# Vector Store pgvector
psycopg2-binary>=2.9.9
pgvector>=0.2.4

# Observabilidad
langsmith>=0.7.6

# Datos
pandas>=2.3.3

# Utilidades
python-dotenv>=1.2.1
```

Verificar que la instalación fue exitosa:

```bash
python -c "import langchain, langgraph, fastapi; print('OK')"
# Debe imprimir: OK
```

---

## 5. Configurar las claves API

### 5.1 El archivo `.env` del repositorio

Al clonar el repositorio ya existe un archivo `.env` con **claves de ejemplo
(falsas)** — los valores `sk-XXXXXXX`. Estas claves permiten que el proyecto
arranque sin errores de sintaxis, pero **no funcionan para llamar a ninguna API**.

```
# Así se ve el .env recién clonado (claves falsas)
DEEPSEEK_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
OPENAI_API_KEY=sk-proj-XXXXXXXX...
```

> **Por qué el `.env` está en el repositorio con claves falsas:**
> Sirve de plantilla lista para completar. Quien clone el repo
> solo necesita reemplazar los `XXXXXXX` con sus claves reales,
> sin tener que crear el archivo desde cero ni adivinar su estructura.

---

### ⚠️ ADVERTENCIA DE SEGURIDAD — Leer antes de continuar

**NUNCA hagas `git add .env` ni `git commit` cuando el archivo
contenga claves API reales.** Si una clave real llega a GitHub
(aunque sea por un segundo), considera que está comprometida:
bórrala en el panel del proveedor y genera una nueva de inmediato.

**Regla de oro:** el `.env` del repositorio siempre debe tener
solo valores `XXXXXXX`. Las claves reales solo viven en tu máquina local.

---

### 5.2 Opción A — Editar `.env` directamente (desarrollo local)

Esta es la forma más rápida para trabajar en tu máquina personal.
Abre el `.env` con cualquier editor y reemplaza los `XXXXXXX` con
tus claves reales:

```
# ── LLM principal ─────────────────────────────────────────────
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat

# ── Claves API — reemplaza XXXXXXX con tus claves reales ──────
ANTHROPIC_API_KEY=sk-ant-api03-tu-clave-real-aqui
OPENAI_API_KEY=sk-proj-tu-clave-real-aqui
DEEPSEEK_API_KEY=sk-tu-clave-real-aqui

# ── Embeddings ────────────────────────────────────────────────
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

# ── API REST ──────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8001

# ── LangSmith (opcional) ──────────────────────────────────────
LANGSMITH_API_KEY=lsv2_pt_tu-clave-langsmith
LANGSMITH_PROJECT=agenteIA-TRM

# ── pgvector / PostgreSQL ─────────────────────────────────────
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=bdvector
PG_USER=postgres
PG_PASSWORD=tu-password-postgresql
PG_COLLECTION=dane_reportes
```

**Después de editar, verificar que git NO detecta el cambio como algo a subir:**

```bash
git diff .env
# Si ves tus claves reales en la salida → NO hagas git add .env
# El archivo puede estar modificado localmente — eso está bien.
# Solo asegúrate de nunca ejecutar git add .env con claves reales.
```

---

### 5.3 Opción B — Variables de entorno del sistema operativo (recomendado para producción)

Esta es la forma **más segura**: las claves reales nunca están en ningún archivo,
solo en la memoria del sistema operativo. `python-dotenv` respeta las variables
de entorno del sistema — si la variable ya existe en el sistema, **no la
sobreescribe** con el valor del `.env`. Así el `.env` puede quedarse con los
`XXXXXXX` sin causar problemas.

**Windows — PowerShell (solo para la sesión actual):**
```powershell
$env:OPENAI_API_KEY    = "sk-proj-tu-clave-real"
$env:DEEPSEEK_API_KEY  = "sk-tu-clave-real"
$env:ANTHROPIC_API_KEY = "sk-ant-api03-tu-clave-real"
$env:PG_PASSWORD       = "tu-password-postgresql"
$env:LANGSMITH_API_KEY = "lsv2_pt_tu-clave-langsmith"
```

**Windows — Permanente (persiste entre reinicios):**
```powershell
# Abrir Panel de control → Sistema → Variables de entorno
# O desde PowerShell como administrador:
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-proj-...", "User")
[System.Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-...", "User")
```

**Linux / macOS — Solo sesión actual:**
```bash
export OPENAI_API_KEY="sk-proj-tu-clave-real"
export DEEPSEEK_API_KEY="sk-tu-clave-real"
export PG_PASSWORD="tu-password-postgresql"
```

**Linux / macOS — Permanente (agregar al final de `~/.bashrc` o `~/.zshrc`):**
```bash
echo 'export OPENAI_API_KEY="sk-proj-tu-clave-real"' >> ~/.bashrc
source ~/.bashrc
```

> **Por qué funciona:** `load_dotenv()` en `config.py` solo establece una variable
> si **todavía no existe** en el entorno. Si el sistema operativo ya tiene
> `OPENAI_API_KEY` con tu clave real, el `.env` con `XXXXXXX` es ignorado
> para esa variable. Puedes dejar el `.env` intacto en el repositorio.

---

**Resumen: ¿cuándo usar cada opción?**

| Situación | Opción recomendada |
|---|---|
| Desarrollo personal en tu PC | A — editar `.env` (sin hacer commit) |
| Servidor de producción / VPS | B — variables de entorno del SO |
| CI/CD (GitHub Actions, etc.) | B — secrets del repositorio |
| Compartir el proyecto con otros | El `.env` del repo con `XXXXXXX` sirve de plantilla |

---

## 6. Estructura de carpetas del proyecto

Después de clonar y configurar, la estructura del proyecto es:

```
agenteIA_TRM/
│
├── .env                      ← claves de ejemplo en el repo; reemplaza con las tuyas localmente
├── .gitignore                ← protege .env y otros archivos sensibles
├── requirements.txt          ← dependencias Python
│
├── config.py                 ← lee .env y expone la configuración
├── database.py               ← acceso a SQLite
├── tools.py                  ← las 6 herramientas del agente
├── agente_langchain.py       ← agente simple (ReAct)
├── agente_langgraph.py       ← agente multi-agente (supervisor)
├── pipeline.py               ← orquesta el agente y mide métricas
├── middleware.py             ← calcula tokens, costos, escribe logs
├── main.py                   ← servidor FastAPI
├── preparar_base.py          ← indexa documentos en pgvector
│
├── datos/                    ← archivos CSV
│   ├── trm_2024.csv
│   ├── comercio_exterior_2024.csv
│   └── exportaciones_sectores_2024.csv
│
├── documentos/               ← archivos para indexar en pgvector
│   ├── boletin_desempleo_2024.txt
│   ├── boletin_ipc_2024.txt
│   ├── cuentas_nacionales_pib_2024.txt
│   └── censo_poblacion_2023.txt
│
├── templates/
│   └── index.html            ← interfaz web Bootstrap 5
│
├── logs/                     ← generado automáticamente al ejecutar
│   └── consultas.jsonl
│
└── tutorial_AgenteIA/        ← esta serie de documentos
```

---

## 7. Crear la base de datos en PostgreSQL

Antes de iniciar el servidor, hay que crear la base de datos donde
pgvector almacenará los vectores.

Abrir una terminal y conectarse a PostgreSQL:

```bash
psql -U postgres
```

Ejecutar los siguientes comandos dentro de psql:

```sql
-- Crear la base de datos
CREATE DATABASE bdvector;

-- Conectarse a ella
\c bdvector

-- Activar la extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verificar que la extensión está activa
SELECT * FROM pg_extension WHERE extname = 'vector';
-- Debe mostrar una fila con el nombre 'vector'

-- Salir
\q
```

Si todo salió bien, PostgreSQL está listo para recibir los vectores
de los documentos.

---

## 8. Indexar los documentos en pgvector

Este paso convierte los archivos de texto de la carpeta `documentos/`
en vectores y los guarda en PostgreSQL. Se ejecuta **una sola vez**
(o cada vez que se agregan nuevos documentos).

```bash
python preparar_base.py
```

La salida esperada es similar a:

```
[pgvector] Conectando a PostgreSQL...
[pgvector] Conexión exitosa · bdvector
[INFO] Procesando: boletin_desempleo_2024.txt
[INFO] Fragmentos generados: 42
[INFO] Embeddings calculados: 42
[INFO] Vectores guardados en pgvector ✓
[INFO] Procesando: boletin_ipc_2024.txt
...
[OK] Base vectorial lista · 4 documentos · 163 fragmentos totales
```

> **¿Cuánto tarda?** Depende de la cantidad de documentos y la
> velocidad de internet (los embeddings se calculan llamando a la
> API de OpenAI). Para los 4 documentos del proyecto, entre 30 y
> 90 segundos.

> **¿Cuánto cuesta?** Los 4 documentos generan aproximadamente
> 163 fragmentos × ~200 tokens = ~32,600 tokens. Con el modelo
> `text-embedding-3-small` el costo es de ~$0.001 USD (menos de
> un centavo de dólar).

---

## 9. Verificar la configuración

Antes de arrancar el servidor, verificar que todo está en orden:

```bash
python -c "
import config
print('Proveedor LLM:  ', config.LLM_PROVIDER)
print('Modelo LLM:     ', config.LLM_MODEL)
print('Vector store:   ', config.VECTOR_STORE_PROVIDER)
print('PG host:        ', config.PG_HOST)
print('API key OpenAI: ', 'OK' if config.OPENAI_API_KEY else 'FALTA')
"
```

Salida esperada:

```
Proveedor LLM:   openai
Modelo LLM:      gpt-4o-mini
Vector store:    pgvector
PG host:         localhost
API key OpenAI:  OK
```

Si `API key OpenAI` muestra `FALTA`, revisar que la clave esté
correctamente escrita en el `.env`.

---

## 10. Iniciar el servidor

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

La opción `--reload` hace que el servidor se reinicie automáticamente
cuando se modifica algún archivo Python. Es útil durante el desarrollo.

La salida esperada es:

```
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

---

## 11. Verificar que el servidor está funcionando

Con el servidor activo, abrir el navegador y verificar tres URLs:

### Interfaz web
```
http://localhost:8001/ui
```
Debe mostrar la interfaz Bootstrap con el chat, los tabs y el sidebar
de configuración.

### Estado del servidor (health check)
```
http://localhost:8001/health
```
Debe mostrar un JSON similar a:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "modelo": "openai/gpt-4o-mini",
  "vector_store": "pgvector",
  "langsmith": false,
  "timestamp": "2025-01-15T10:30:00"
}
```

### Documentación automática Swagger
```
http://localhost:8001/docs
```
Muestra todos los endpoints disponibles con la posibilidad de
probarlos directamente desde el navegador.

---

## 12. Primera prueba del agente

Con la interfaz abierta en `http://localhost:8001/ui`:

1. En el sidebar, verificar que el proveedor y modelo son correctos.
2. En el tab **Chat**, escribir una pregunta de prueba:
   ```
   ¿Cuántos fragmentos hay indexados en la base vectorial?
   ```
3. Seleccionar backend **LangChain**.
4. Hacer clic en **Consultar al Agente**.

La respuesta debe aparecer en pocos segundos junto con las métricas
(latencia, tokens y costo estimado).

---

## 13. Solución de problemas frecuentes

### Error: `OPENAI_API_KEY not found`
El archivo `.env` no tiene la clave o no está en la carpeta correcta.
Verificar que `.env` está en la raíz del proyecto (misma carpeta que
`main.py`) y que contiene `OPENAI_API_KEY=sk-proj-...`.

### Error: `could not connect to server` (PostgreSQL)
PostgreSQL no está corriendo. En Windows:
```bash
# Iniciar el servicio PostgreSQL
net start postgresql-x64-15
# (el número puede variar según la versión instalada)
```

### Error: `relation "langchain_pg_embedding" does not exist`
El script `preparar_base.py` no se ha ejecutado todavía, o se ejecutó
con una base de datos diferente. Ejecutar:
```bash
python preparar_base.py
```

### Error: `ModuleNotFoundError`
El entorno virtual no está activo o las dependencias no se instalaron.
```bash
.venv\Scripts\Activate.ps1    # activar entorno
pip install -r requirements.txt  # reinstalar dependencias
```

### La interfaz web no carga
Verificar que el servidor está corriendo y que la URL es exactamente
`http://localhost:8001/ui` (con `/ui` al final).

---

## Referencias

1. Python — Virtual Environments and Packages.
   https://docs.python.org/3/tutorial/venv.html

2. pip — Package Installer for Python.
   https://pip.pypa.io/en/stable/

3. python-dotenv — Read key-value pairs from a .env file.
   https://pypi.org/project/python-dotenv/

4. Uvicorn — An ASGI web server implementation for Python.
   https://www.uvicorn.org/

5. pgvector — Open-source vector similarity search for Postgres.
   https://github.com/pgvector/pgvector

6. PostgreSQL Documentation.
   https://www.postgresql.org/docs/

---

## Pasos Git

```bash
git add tutorial_AgenteIA/03_configuracion_entorno.md
git commit -m "docs: agrega documento 03 - configuracion del entorno"
git push origin main
```

> **Siguiente documento:** `04_preparacion_datos.md` — Estructura de
> los archivos CSV, preparación de documentos PDF/TXT, y cómo ejecutar
> `preparar_base.py` para indexar en pgvector.
