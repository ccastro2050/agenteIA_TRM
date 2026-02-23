# 08 — Interfaz Web Bootstrap 5

## Qué construimos en este documento

La capa de presentación del agente: una **Single-Page Application (SPA)** en HTML puro
servida directamente por FastAPI. Sin React, sin Vue, sin build step — solo Bootstrap 5,
JavaScript vanilla y tres librerías CDN.

**Archivos de este documento:**

```
agenteIA_TRM/
├── templates/
│   └── index.html           ← SPA completa (Bootstrap 5 + JS vanilla)
├── langgraph_to_n8n.py      ← Genera el JSON del workflow para n8n
└── main.py                  ← + endpoints /api/archivos /api/upload /api/n8n-workflow
```

---

## Por qué HTML en vez de Streamlit

El capítulo anterior usó FastAPI + Jinja2 para servir la UI. Podríamos haber usado
Streamlit, Gradio o Panel, pero el HTML puro tiene ventajas en producción:

| Aspecto | HTML / Bootstrap | Streamlit |
|---|---|---|
| Proceso extra | No (el mismo FastAPI) | Sí (proceso Python aparte) |
| Puerto extra | No (puerto 8001) | Sí (puerto 8501) |
| Personalización CSS | Total | Limitada |
| Despliegue en servidor | 1 servicio | 2 servicios |
| Control del DOM | Total | Nulo |
| Curva de aprendizaje | HTML/JS estándar | API propia de Streamlit |

En el contexto de este proyecto, la UI es parte de la API — no un proceso separado.

---

## Concepto nuevo: SPA (Single-Page Application)

Una **SPA** es una aplicación web que carga **una sola página HTML** y manipula el DOM
para simular navegación entre secciones. No hay recarga del navegador al cambiar de tab.

```
Carga inicial → GET /ui → HTML completo → JavaScript toma el control
Acción usuario → JavaScript llama API → actualiza el DOM → sin recarga
```

En `index.html` los tabs no son páginas distintas — son `<div>` con la clase
`d-none` (Bootstrap) que se muestran u ocultan con la función `showTab()`:

```javascript
function showTab(name) {
  ALL_TABS.forEach(t => {
    const id = 'tab' + t.charAt(0).toUpperCase() + t.slice(1);
    document.getElementById(id).classList.toggle('d-none', t !== name);
  });
  // ...
}
```

`classList.toggle('d-none', condición)` ← agrega `d-none` si la condición es `true`,
la remueve si es `false`. Así se logra mostrar/ocultar sin recargar.

---

## Estructura del HTML: dos columnas

El layout usa el **grid de Bootstrap 5** (sistema de 12 columnas):

```
<div class="row g-0">
  <div class="col-xl-2 col-lg-3 col-md-4 sidebar">   ← Sidebar: 2/12 en XL
    ...
  </div>
  <div class="col main-content">                      ← Contenido: resto
    ...
  </div>
</div>
```

`g-0` elimina el gutter (espacio entre columnas).
`col` sin número toma el espacio restante automáticamente.

### El sidebar contiene

```
┌─ Configuración LLM ──────────────┐
│  Proveedor ▼  (select)           │
│  Modelo ▼     (select dinámico)  │
│  API Key 🔑   (password input)   │
├─ Vector Store ───────────────────┤
│  pgvector (PostgreSQL) [fijo]    │
├─ LangSmith ──────────────────────┤
│  API Key  ▼                      │
│  Proyecto (input text)           │
│  [Guardar configuración]         │
├─ Estado ─────────────────────────┤
│  ● anthropic / claude-sonnet-4-6 │
│  🗄 PGVECTOR                     │
├─ Costos USD/1K tokens ───────────┤
│  Input  $0.00300                 │
│  Output $0.01500                 │
└──────────────────────────────────┘
```

### El área principal tiene 6 tabs

| Tab | Función |
|---|---|
| Chat | Envía preguntas, muestra respuesta con métricas |
| Prompts | Acordeón con los 6 prompts editables (SQLite) |
| Métricas | KPIs operativos: latencia, costo, tokens |
| Historial | Tabla de consultas + export CSV |
| Archivos | Gestión de CSVs y documentos con drag & drop |
| n8n | Visualiza e importa el workflow en n8n |

---

## Concepto nuevo: Fetch API

**`fetch()`** es la API nativa del navegador para hacer peticiones HTTP asíncronas
(reemplaza a `XMLHttpRequest`). Se combina con `async/await` para código legible:

```javascript
// Patrón básico GET
const datos = await fetch('/health').then(r => r.json());

// Patrón POST con JSON
const r = await fetch('/consulta', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ pregunta, temperatura, backend, prompts }),
});
const d = await r.json();
```

### El patrón try/catch/finally

La función `enviarConsulta()` ilustra el manejo completo de errores:

```javascript
async function enviarConsulta() {
  // 1. Activar spinner (UI loading)
  document.getElementById('btnConsultar').disabled = true;
  document.getElementById('spinConsulta').classList.remove('d-none');

  try {
    const r = await fetch('/consulta', { method: 'POST', ... });
    const d = await r.json();

    if (!r.ok) {
      // 2a. Error HTTP (4xx / 5xx) — muestra el mensaje de la API
      mostrarError(r.status, d.detail);
      return;
    }
    // 2b. Respuesta exitosa
    mostrarRespuesta(d);

  } catch (e) {
    // 3. Error de red (sin conexión, timeout)
    mostrarErrorRed(e.message);
  } finally {
    // 4. Siempre: desactivar spinner
    document.getElementById('btnConsultar').disabled = false;
    document.getElementById('spinConsulta').classList.add('d-none');
  }
}
```

El bloque `finally` se ejecuta **siempre**, incluso si hubo error. Garantiza que
el spinner nunca quede "colgado".

---

## Concepto nuevo: `marked.js` — renderizar Markdown

Los LLMs devuelven texto en formato Markdown (`**negrita**`, listas, tablas).
Para mostrarlo formateado en el navegador usamos **marked.js**:

```html
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
```

```javascript
// Convertir Markdown a HTML y mostrar en el DOM
document.getElementById('boxRespuesta').innerHTML = marked.parse(d.respuesta || '');
```

`marked.parse()` convierte el texto Markdown a HTML. Se asigna con `innerHTML`
para que el navegador lo renderice como HTML real.

> **Nota de seguridad:** `innerHTML` es seguro aquí porque la fuente es el propio LLM
> (no input del usuario), y `marked.js` escapa el HTML por defecto.

---

## Concepto nuevo: `escHtml()` — prevención de XSS

Cuando se muestra **input del usuario** en el DOM, hay que escapar los caracteres
HTML especiales para evitar XSS (Cross-Site Scripting):

```javascript
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

Se usa en los textareas de prompts (`innerHTML` en el acordeón) y en los
nombres de archivos de la lista de la carpeta `documentos/`.

**Regla práctica:** usa `textContent` para texto plano (automáticamente seguro),
usa `innerHTML + escHtml()` cuando necesitas mezclar HTML con datos del usuario.

---

## El acordeón de prompts

El tab **Prompts** construye dinámicamente un acordeón Bootstrap 5 con los 6 prompts.
La función `buildAccordion()` itera sobre `PROMPT_ORDER` y crea el HTML:

```javascript
const PROMPT_META = {
  langchain_main:         { label: 'LangChain — Prompt principal',  icon: '...', color: 'primary'   },
  langgraph_supervisor:   { label: 'LangGraph — Supervisor',         icon: '...', color: 'success'   },
  langgraph_trm:          { label: 'LangGraph — Agente TRM',        icon: '...', color: 'warning'   },
  langgraph_datos:        { label: 'LangGraph — Agente Datos',      icon: '...', color: 'info'      },
  langgraph_rag:          { label: 'LangGraph — Agente RAG',        icon: '...', color: 'secondary' },
  langgraph_sintetizador: { label: 'LangGraph — Sintetizador',      icon: '...', color: 'danger'    },
};
```

Cada item del acordeón tiene un `<textarea>` con la clase `prompt-textarea`
(fuente monospace, redimensionable), y un botón **Guardar** que llama a `savePrompt()`.

### Flujo de prompts

```
1. Carga de página:  GET /api/prompts → curPrompts (dict JS)
2. buildAccordion(): rellena cada textarea con curPrompts[nombre]
3. Usuario edita → hace clic en Guardar:
   PUT /api/prompts/{nombre} {contenido: textarea.value}
   → SQLite → persiste entre sesiones
4. Consultar al agente:
   getPromptsFromUI() → recolecta todos los textareas
   POST /consulta { prompts: {todos los prompts} }
   → pipeline → agente usa los prompts del request
```

Los prompts del textarea **viajan en cada POST /consulta** — el agente los recibe
como parámetro y los usa en vez de los que estén en SQLite. Esto permite
experimentar con cambios sin guardarlos permanentemente.

---

## Concepto nuevo: `FormData` para subir archivos

El tab **Archivos** usa `FormData` para subir archivos con `multipart/form-data`:

```javascript
async function uploadFiles(carpeta, files) {
  for (const file of files) {
    const fd = new FormData();
    fd.append('archivo', file);                        // nombre del campo
    const r = await fetch(`/api/upload/${carpeta}`, {
      method: 'POST',
      body: fd,                                        // sin Content-Type manual
    });
    // ...
  }
}
```

> No se escribe `Content-Type: multipart/form-data` manualmente — el navegador lo
> agrega automáticamente con el `boundary` correcto cuando el body es `FormData`.

En el lado del servidor (FastAPI):

```python
@app.post("/api/upload/{carpeta}")
async def upload_archivo(carpeta: str, archivo: UploadFile = File(...)) -> dict:
    destino = (_DATOS_DIR if carpeta == "datos" else _DOCS_DIR) / archivo.filename
    with open(destino, "wb") as f:
        shutil.copyfileobj(archivo.file, f)
    return {"ok": True, "nombre": archivo.filename}
```

`UploadFile` es la clase de FastAPI para recibir archivos. `shutil.copyfileobj`
copia el stream del archivo al destino sin cargarlo completo en memoria.

### Drag & drop

Las zonas de drop escuchan tres eventos del navegador:

```javascript
ondragover  → e.preventDefault()   // permite soltar (sin esto no funciona)
ondragleave → resetear estilos
ondrop      → e.dataTransfer.files → uploadFiles(carpeta, files)
```

---

## Los nuevos endpoints en main.py

```python
# Listar archivos
GET  /api/archivos                    → {datos: [...], documentos: [...]}

# Subir archivo (multipart/form-data, campo "archivo")
POST /api/upload/{carpeta}            → {ok: true, nombre: str}

# Eliminar archivo
DELETE /api/archivos/{carpeta}/{nombre} → {ok: true, nombre: str}

# Workflow n8n (lee langgraph_to_n8n.json)
GET  /api/n8n-workflow                → dict (JSON del workflow)
```

Los tres primeros usan `config.BASE_DIR / "datos"` y `config.BASE_DIR / "documentos"`
como rutas absolutas — no dependen del directorio de trabajo actual.

---

## Dark mode sin CSS extra

Bootstrap 5.3 soporta temas nativamente con el atributo `data-bs-theme`:

```html
<html lang="es" data-bs-theme="light">   <!-- tema inicial -->
```

```javascript
function toggleTheme() {
  const html = document.documentElement;
  const dark = html.getAttribute('data-bs-theme') === 'dark';
  html.setAttribute('data-bs-theme', dark ? 'light' : 'dark');
  document.getElementById('themeIcon').className = dark ? 'bi bi-moon-fill' : 'bi bi-sun-fill';
}
```

Cambiar `data-bs-theme="dark"` hace que todos los componentes Bootstrap (cards,
tablas, navbar, inputs) cambien automáticamente al tema oscuro — sin escribir
una sola línea de CSS adicional.

---

## Concepto nuevo: Toast notifications

Los toasts de Bootstrap son notificaciones temporales que aparecen en la esquina
inferior derecha sin interrumpir el flujo del usuario:

```html
<div class="toast-container position-fixed bottom-0 end-0 p-3">
  <div id="toast" class="toast" role="alert">
    <div class="toast-body">
      <i class="bi" id="toastIcon"></i>
      <span id="toastMsg"></span>
    </div>
  </div>
</div>
```

```javascript
function toast(title, msg, ok) {
  document.getElementById('toastMsg').textContent = title + ' — ' + msg;
  // Color según éxito/error
  el.className = 'toast align-items-center border-0 text-bg-' + (ok ? 'light' : 'danger');
  new bootstrap.Toast(el, { delay: 3500 }).show();   // auto-cierra en 3.5 s
}
```

Se usa en toda la UI: al guardar config, al guardar un prompt, al subir archivos,
al copiar el JSON de n8n, y cuando la consulta al agente falla.

---

## langgraph_to_n8n.py — el exportador

El script genera un archivo `langgraph_to_n8n.json` con un workflow n8n de 4 nodos:

```
Manual Trigger → Definir pregunta → Consultar Agente IA → Extraer resultado
                                         ↓
                                    POST /consulta
                                    { pregunta, backend, temperatura }
                                         ↓
                                    { respuesta, latencia_ms, tokens_total, ... }
```

El workflow es una representación en JSON del mismo pipeline que ya definimos con
LangGraph — pero en el formato que entiende n8n, permitiendo conectar el agente con
cualquier sistema externo (Slack, Gmail, Google Sheets, bases de datos, etc.).

```bash
python langgraph_to_n8n.py                        # URL: http://localhost:8001
python langgraph_to_n8n.py --host http://mi-api   # URL personalizada
```

---

## Librerías CDN usadas

```html
<!-- Bootstrap 5.3.3 — estilos + componentes JS (grid, accordion, toast, dark mode) -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js">

<!-- Bootstrap Icons 1.11.3 — iconos SVG como fuente web -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">

<!-- marked.js 12.0.0 — convierte Markdown a HTML -->
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js">
```

El uso de CDN (jsDelivr) significa **cero dependencias npm**, cero build step y
cacheo automático en el navegador del usuario.

---

## Verificación completa

```bash
# 1. Iniciar la API
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 2. Abrir la UI
# → http://localhost:8001/ui

# 3. Verificar que el sidebar muestra pgvector fijo (no un dropdown)

# 4. Tab Chat — enviar una pregunta:
#    ¿Cuánto está el dólar hoy?  (Ctrl+Enter)
#    → debe aparecer respuesta + badges de latencia/tokens/costo

# 5. Tab Prompts — editar el prompt del supervisor:
#    Agregar texto al inicio → Guardar
#    Hacer consulta nueva → verificar que el agente usa el prompt modificado

# 6. Tab Métricas — clic en Actualizar:
#    → KPIs: total consultas, latencia p50, costo total, tokens total

# 7. Tab Historial — verificar la consulta del paso 4 aparece

# 8. Tab Archivos — arrastrar un CSV a datos/:
#    → aparece en la lista → badge aumenta

# 9. Generar el workflow n8n:
python langgraph_to_n8n.py
#    → Tab n8n → "Cargar JSON" → verifica los 4 nodos → "Copiar"

# 10. Dark mode — botón luna en navbar → toda la UI cambia de tema
```

---

## Conceptos nuevos en este documento

| Concepto | Explicación |
|---|---|
| **SPA** | Una página, múltiples vistas — el JS manipula el DOM |
| **Fetch API** | HTTP asíncrono en el navegador con `async/await` |
| **try/catch/finally** | Manejo robusto de errores — `finally` siempre corre |
| **marked.js** | Convierte Markdown a HTML para renderizar respuestas |
| **escHtml()** | Escapa HTML para prevenir XSS en datos del usuario |
| **FormData** | Objeto JS para subir archivos con multipart/form-data |
| **UploadFile / File** | FastAPI recibe archivos del formulario multipart |
| **shutil.copyfileobj** | Copia streams de archivo sin cargarlos en memoria |
| **drag & drop API** | `ondragover`, `ondragleave`, `ondrop` del navegador |
| **data-bs-theme** | Bootstrap 5.3 cambia todo el tema con un atributo HTML |
| **Toast Bootstrap** | Notificaciones temporales sin interrumpir el usuario |
| **`classList.toggle`** | Agrega/remueve clase CSS según condición booleana |

---

## Resumen del proyecto completo

Con este documento el proyecto `agenteIA_TRM` está **completo**:

```
agenteIA_TRM/
├── .env.example              ← Variables de entorno (sin keys reales)
├── .gitignore                ← Protege .env, *.db, logs/, __pycache__/
├── requirements.txt          ← Dependencias Python
├── config.py                 ← Configuración multi-LLM, solo pgvector
├── vectorstore_factory.py    ← Crea/carga pgvector
├── preparar_base.py          ← Indexa documentos en pgvector
├── tools.py                  ← 6 herramientas en 3 grupos (TRM, Datos, RAG)
├── agente_langchain.py       ← Agente ReAct (LangChain)
├── agente_langgraph.py       ← Multi-agente supervisor (LangGraph)
├── database.py               ← SQLite: prompts, config, historial
├── middleware.py             ← Tokens, costos, logs JSONL, métricas
├── pipeline.py               ← Grafo LangGraph de producción (3 nodos)
├── main.py                   ← API FastAPI (12+ endpoints)
├── langgraph_to_n8n.py       ← Exporta workflow para n8n
├── templates/
│   └── index.html            ← UI Bootstrap 5 (SPA)
├── datos/                    ← CSVs: TRM, comercio exterior
├── documentos/               ← TXTs: reportes DANE
└── tutorial_AgenteIA/        ← Esta serie de documentos
    ├── 01_introduccion.md
    ├── ...
    └── 08_interfaz_web.md    ← Este documento
```

---

## Commit y push

```bash
cd agenteIA_TRM

git add templates/index.html langgraph_to_n8n.py main.py \
        tutorial_AgenteIA/08_interfaz_web.md

git commit -m "doc 08: UI Bootstrap 5 + gestión de archivos + n8n workflow"

git push origin main
```

---

*Proyecto agente_IA_TRM — USB Medellín*
*Documento 8 de 8 — Serie tutorial_AgenteIA*
