"""
main.py — API REST del Agente (FastAPI)
=======================================
Proyecto agente_IA_TRM · USB Medellín

Endpoints:
  POST /consulta           → envía una pregunta al agente
  GET  /health             → estado del servicio
  GET  /metricas           → métricas operativas (latencia, costo, tokens)
  GET  /historial          → últimas N consultas
  GET  /version            → versión y configuración de la API
  GET  /ui                 → interfaz web Bootstrap 5
  GET  /docs               → documentación interactiva (Swagger UI)

  GET  /api/prompts        → obtener prompts de SQLite
  PUT  /api/prompts/{nombre} → guardar un prompt
  GET  /api/config         → configuración actual
  POST /api/config         → guardar configuración
  GET  /api/modelos        → modelos disponibles por proveedor

Uso (desarrollo):
    python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

Ejemplo con curl:
    curl -X POST http://localhost:8001/consulta \\
         -H "Content-Type: application/json" \\
         -d '{"pregunta": "¿Cuánto está el dólar hoy?"}'
"""

import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime
from typing import Optional
import csv
import io
import json
import shutil

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import config
import middleware
import pipeline
import database

# ---------------------------------------------------------------------------
# Activar LangSmith si está configurado
# ---------------------------------------------------------------------------

if config.LANGSMITH_ENABLED:
    import os
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]     = config.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"]     = config.LANGSMITH_PROJECT


# ---------------------------------------------------------------------------
# Aplicación FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESC,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))


@app.on_event("startup")
async def startup_event():
    """Inicializa SQLite al arrancar la API."""
    database.init_db()


# ---------------------------------------------------------------------------
# Modelos Pydantic — Contratos de la API
# ---------------------------------------------------------------------------

class ConsultaRequest(BaseModel):
    """Cuerpo del request POST /consulta."""
    pregunta: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Pregunta sobre TRM, comercio exterior o estadísticas DANE",
        example="¿Cuál es el TRM actual y cómo afecta las exportaciones?",
    )
    temperatura: Optional[float] = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Creatividad del LLM: 0.0 = determinista, 1.0 = creativo",
    )
    backend: Optional[str] = Field(
        default="langgraph",
        description="Motor del agente: 'langchain' o 'langgraph'",
    )
    prompts: Optional[dict] = Field(
        default=None,
        description="Prompts personalizados para esta consulta (sobreescriben los de SQLite)",
    )


class ConsultaResponse(BaseModel):
    """Cuerpo del response POST /consulta."""
    respuesta:          str
    latencia_ms:        float
    tokens_in:          int
    tokens_out:         int
    tokens_total:       int
    costo_estimado_usd: float
    timestamp:          str
    modelo:             str
    backend:            str
    version:            str


class HealthResponse(BaseModel):
    """Cuerpo del response GET /health."""
    status:       str
    version:      str
    modelo:       str
    vector_store: str
    langsmith:    bool
    timestamp:    str


class VersionResponse(BaseModel):
    """Cuerpo del response GET /version."""
    api_version:          str
    api_title:            str
    llm_provider:         str
    llm_model:            str
    embedding_provider:   str
    vector_store:         str
    langsmith_project:    Optional[str]
    costos_por_1k_tokens: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/consulta", response_model=ConsultaResponse, tags=["Agente"],
          summary="Consultar al agente")
async def consultar(req: ConsultaRequest) -> ConsultaResponse:
    """Procesa una consulta a través del pipeline de producción."""
    backend = req.backend if req.backend in ("langchain", "langgraph") else "langgraph"

    # Activar LangSmith dinámicamente (SQLite > .env)
    import os
    db_cfg  = database.get_all_config()
    ls_key  = db_cfg.get("langsmith_api_key", "") or config.LANGSMITH_API_KEY
    ls_proj = db_cfg.get("langsmith_project",  "") or config.LANGSMITH_PROJECT
    if ls_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"]     = ls_key
        os.environ["LANGCHAIN_PROJECT"]     = ls_proj
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"

    try:
        resultado = pipeline.procesar_consulta(
            pregunta=req.pregunta,
            temperatura=req.temperatura,
            backend=backend,
            prompts=req.prompts,
        )
    except Exception as e:
        tipo = type(e).__name__
        raise HTTPException(status_code=500, detail=f"[{tipo}] {e}")

    return ConsultaResponse(
        respuesta=resultado["respuesta"],
        latencia_ms=resultado["latencia_ms"],
        tokens_in=resultado["tokens_in"],
        tokens_out=resultado["tokens_out"],
        tokens_total=resultado["tokens_total"],
        costo_estimado_usd=resultado["costo_usd"],
        timestamp=resultado["timestamp"],
        modelo=resultado["modelo"],
        backend=resultado["backend"],
        version=config.API_VERSION,
    )


@app.get("/health", response_model=HealthResponse, tags=["Operaciones"],
         summary="Estado del servicio")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=config.API_VERSION,
        modelo=f"{config.LLM_PROVIDER}/{config.LLM_MODEL}",
        vector_store=config.VECTOR_STORE_PROVIDER,
        langsmith=config.LANGSMITH_ENABLED,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/metricas", tags=["Operaciones"], summary="Métricas operativas")
async def metricas() -> dict:
    return middleware.calcular_metricas()


@app.get("/historial", tags=["Operaciones"], summary="Historial de consultas")
async def historial(n: int = 50) -> list:
    if n < 1 or n > 9999:
        raise HTTPException(status_code=400, detail="n debe estar entre 1 y 9999")
    return middleware.obtener_historial(n=n)


@app.get("/historial/export", tags=["Operaciones"],
         summary="Exportar historial como CSV")
async def exportar_historial_csv():
    registros = database.get_historial(n=9999)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "timestamp", "pregunta", "latencia_ms", "tokens_out",
        "costo_usd", "modelo", "backend"
    ])
    writer.writeheader()
    for r in reversed(registros):
        writer.writerow({
            "timestamp":   r["timestamp"],
            "pregunta":    r["pregunta"],
            "latencia_ms": r["latencia_ms"],
            "tokens_out":  r.get("tokens_out", 0),
            "costo_usd":   r["costo_usd"],
            "modelo":      r.get("modelo", ""),
            "backend":     r.get("backend", ""),
        })
    output.seek(0)
    nombre = f"historial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@app.get("/version", response_model=VersionResponse, tags=["Operaciones"],
         summary="Versión y configuración")
async def version() -> VersionResponse:
    costos = config.COSTOS_POR_PROVEEDOR.get(
        config.LLM_PROVIDER, {"input": 0.0, "output": 0.0}
    )
    return VersionResponse(
        api_version=config.API_VERSION,
        api_title=config.API_TITLE,
        llm_provider=config.LLM_PROVIDER,
        llm_model=config.LLM_MODEL,
        embedding_provider=config.EMBEDDING_PROVIDER,
        vector_store=config.VECTOR_STORE_PROVIDER,
        langsmith_project=config.LANGSMITH_PROJECT if config.LANGSMITH_ENABLED else None,
        costos_por_1k_tokens=costos,
    )


# ---------------------------------------------------------------------------
# UI Bootstrap
# ---------------------------------------------------------------------------

@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui(request: Request):
    """Sirve la interfaz Bootstrap 5."""
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# API de configuración y prompts
# ---------------------------------------------------------------------------

@app.get("/api/prompts", tags=["Configuración UI"],
         summary="Obtener todos los prompts")
async def get_prompts() -> dict:
    return database.get_all_prompts()


@app.put("/api/prompts/{nombre}", tags=["Configuración UI"],
         summary="Guardar un prompt")
async def save_prompt(nombre: str, body: dict) -> dict:
    contenido = body.get("contenido", "")
    if not contenido:
        raise HTTPException(status_code=400, detail="El campo 'contenido' es requerido")
    database.save_prompt(nombre, contenido)
    return {"ok": True, "nombre": nombre}


@app.get("/api/config", tags=["Configuración UI"],
         summary="Obtener configuración UI")
async def get_config_ui() -> dict:
    db_cfg  = database.get_all_config()
    ls_key  = db_cfg.get("langsmith_api_key", "") or config.LANGSMITH_API_KEY
    ls_proj = db_cfg.get("langsmith_project",  "") or config.LANGSMITH_PROJECT
    return {
        "llm_provider":       db_cfg.get("llm_provider",      config.LLM_PROVIDER),
        "llm_model":          db_cfg.get("llm_model",          config.LLM_MODEL),
        "vector_store":       db_cfg.get("vector_store",       config.VECTOR_STORE_PROVIDER),
        "embedding_provider": db_cfg.get("embedding_provider", config.EMBEDDING_PROVIDER),
        "langsmith_project":  ls_proj,
        "langsmith_enabled":  bool(ls_key),
        "langsmith_api_key":  "***" if ls_key else "",
        "api_version":        config.API_VERSION,
    }


@app.post("/api/config", tags=["Configuración UI"],
          summary="Guardar configuración UI")
async def save_config_ui(body: dict) -> dict:
    saved = []
    for clave, valor in body.items():
        if valor is not None and str(valor).strip():
            database.save_config(clave, str(valor))
            saved.append(clave)
    return {"ok": True, "guardadas": saved}


@app.get("/api/modelos", tags=["Configuración UI"],
         summary="Modelos disponibles por proveedor")
async def get_modelos() -> dict:
    return config.MODELOS_POR_PROVEEDOR


# ---------------------------------------------------------------------------
# Rutas de datos y documentos
# ---------------------------------------------------------------------------

_DATOS_DIR = config.BASE_DIR / "datos"
_DOCS_DIR  = config.BASE_DIR / "documentos"


@app.get("/api/archivos", tags=["Archivos"], summary="Listar archivos de datos y documentos")
async def listar_archivos() -> dict:
    """Retorna la lista de archivos en datos/ y documentos/."""
    def _info(path) -> list:
        if not path.exists():
            return []
        return [
            {
                "nombre":    f.name,
                "tamaño_kb": round(f.stat().st_size / 1024, 1),
                "modificado": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            }
            for f in sorted(path.iterdir())
            if f.is_file() and not f.name.startswith(".")
        ]
    return {"datos": _info(_DATOS_DIR), "documentos": _info(_DOCS_DIR)}


@app.post("/api/upload/{carpeta}", tags=["Archivos"], summary="Subir un archivo")
async def upload_archivo(carpeta: str, archivo: UploadFile = File(...)) -> dict:
    """Copia el archivo a datos/ o documentos/ según el parámetro carpeta."""
    if carpeta not in ("datos", "documentos"):
        raise HTTPException(status_code=400, detail="carpeta debe ser 'datos' o 'documentos'")
    destino = (_DATOS_DIR if carpeta == "datos" else _DOCS_DIR) / archivo.filename
    with open(destino, "wb") as f:
        shutil.copyfileobj(archivo.file, f)
    return {"ok": True, "nombre": archivo.filename}


@app.delete("/api/archivos/{carpeta}/{nombre}", tags=["Archivos"], summary="Eliminar un archivo")
async def eliminar_archivo(carpeta: str, nombre: str) -> dict:
    """Elimina un archivo de datos/ o documentos/."""
    if carpeta not in ("datos", "documentos"):
        raise HTTPException(status_code=400, detail="carpeta inválida")
    ruta = (_DATOS_DIR if carpeta == "datos" else _DOCS_DIR) / nombre
    if not ruta.exists() or not ruta.is_file():
        raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {nombre}")
    ruta.unlink()
    return {"ok": True, "nombre": nombre}


# ---------------------------------------------------------------------------
# Workflow n8n
# ---------------------------------------------------------------------------

@app.get("/api/n8n-workflow", tags=["n8n"], summary="Workflow JSON para importar en n8n")
async def get_n8n_workflow() -> dict:
    """Retorna el JSON del workflow n8n generado por langgraph_to_n8n.py."""
    json_path = config.BASE_DIR / "langgraph_to_n8n.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado. Ejecuta primero: python langgraph_to_n8n.py",
        )
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "mensaje": f"{config.API_TITLE} v{config.API_VERSION}",
        "docs":    "/docs",
        "health":  "/health",
        "ui":      "/ui",
    }


# ---------------------------------------------------------------------------
# Punto de entrada (desarrollo)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    config.validate()

    print(f"\n{'='*65}")
    print(f"  {config.API_TITLE}  v{config.API_VERSION}")
    print(f"{'='*65}")
    print(f"  UI    : http://localhost:{config.PORT}/ui")
    print(f"  Docs  : http://localhost:{config.PORT}/docs")
    print(f"  Health: http://localhost:{config.PORT}/health")
    print(f"  LLM   : {config.LLM_PROVIDER} / {config.LLM_MODEL}")
    if config.LANGSMITH_ENABLED:
        print(f"  Trazas: https://smith.langchain.com ({config.LANGSMITH_PROJECT})")
    print(f"{'='*65}\n")

    uvicorn.run("main:app", host=config.HOST, port=config.PORT,
                reload=True, log_level="info")
