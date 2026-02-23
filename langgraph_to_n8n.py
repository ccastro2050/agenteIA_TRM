"""
langgraph_to_n8n.py — Exporta el pipeline a un workflow importable en n8n
==========================================================================
Proyecto agente_IA_TRM · USB Medellín

Genera el archivo langgraph_to_n8n.json con un workflow n8n que:
  1. Recibe una pregunta via Manual Trigger (para pruebas) o Webhook (producción)
  2. Hace POST /consulta a la API FastAPI con backend langgraph
  3. Extrae la respuesta y las métricas (latencia, tokens, costo)

Uso:
    python langgraph_to_n8n.py
    python langgraph_to_n8n.py --host http://mi-servidor:8001

El archivo generado se puede ver e importar desde la UI en /ui → tab n8n.
"""

import json
import sys
import argparse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config


def generar_workflow(host: str = "http://localhost:8001") -> dict:
    """Construye el diccionario del workflow n8n."""
    return {
        "name": f"Agente IA TRM — {config.API_VERSION}",
        "nodes": [
            # ── Nodo 1: Manual Trigger (prueba sin webhook) ────────────────
            {
                "id": "n1",
                "name": "Manual Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {},
            },
            # ── Nodo 2: Set — define la pregunta de ejemplo ────────────────
            {
                "id": "n2",
                "name": "Definir pregunta",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [460, 300],
                "parameters": {
                    "mode": "manual",
                    "fields": {
                        "values": [
                            {
                                "name": "pregunta",
                                "type": "stringValue",
                                "value": "¿Cuánto está el dólar hoy y cuál es la tendencia del TRM?",
                            },
                            {
                                "name": "backend",
                                "type": "stringValue",
                                "value": "langgraph",
                            },
                            {
                                "name": "temperatura",
                                "type": "numberValue",
                                "value": 0.2,
                            },
                        ]
                    },
                },
            },
            # ── Nodo 3: HTTP Request → POST /consulta ──────────────────────
            {
                "id": "n3",
                "name": "Consultar Agente IA",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [680, 300],
                "parameters": {
                    "method": "POST",
                    "url": f"{host}/consulta",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "Content-Type", "value": "application/json"}
                        ]
                    },
                    "sendBody": True,
                    "contentType": "json",
                    "body": {
                        "pregunta":   "={{ $json.pregunta }}",
                        "backend":    "={{ $json.backend }}",
                        "temperatura": "={{ $json.temperatura }}",
                    },
                    "options": {"timeout": 120000},
                },
            },
            # ── Nodo 4: Set — extrae campos de la respuesta ─────────────────
            {
                "id": "n4",
                "name": "Extraer resultado",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [900, 300],
                "parameters": {
                    "mode": "manual",
                    "fields": {
                        "values": [
                            {
                                "name": "respuesta",
                                "type": "stringValue",
                                "value": "={{ $json.respuesta }}",
                            },
                            {
                                "name": "latencia_ms",
                                "type": "numberValue",
                                "value": "={{ $json.latencia_ms }}",
                            },
                            {
                                "name": "tokens_total",
                                "type": "numberValue",
                                "value": "={{ $json.tokens_total }}",
                            },
                            {
                                "name": "costo_usd",
                                "type": "numberValue",
                                "value": "={{ $json.costo_estimado_usd }}",
                            },
                            {
                                "name": "modelo",
                                "type": "stringValue",
                                "value": "={{ $json.modelo }}",
                            },
                            {
                                "name": "backend_usado",
                                "type": "stringValue",
                                "value": "={{ $json.backend }}",
                            },
                        ]
                    },
                },
            },
        ],
        "connections": {
            "Manual Trigger": {
                "main": [[{"node": "Definir pregunta", "type": "main", "index": 0}]]
            },
            "Definir pregunta": {
                "main": [[{"node": "Consultar Agente IA", "type": "main", "index": 0}]]
            },
            "Consultar Agente IA": {
                "main": [[{"node": "Extraer resultado", "type": "main", "index": 0}]]
            },
        },
        "settings": {
            "executionOrder": "v1",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "meta": {
            "instanceId": "agenteIA-TRM",
            "description": (
                f"Workflow generado automáticamente por langgraph_to_n8n.py "
                f"— Agente IA TRM v{config.API_VERSION} · USB Medellín"
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Genera el workflow n8n para el Agente IA TRM"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8001",
        help="URL base de la API FastAPI (default: http://localhost:8001)",
    )
    args = parser.parse_args()

    workflow = generar_workflow(host=args.host)

    output_path = config.BASE_DIR / "langgraph_to_n8n.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, ensure_ascii=False, indent=2)

    print(f"Workflow generado: {output_path}")
    print(f"  Nodos  : {len(workflow['nodes'])}")
    print(f"  API    : {args.host}/consulta")
    print(f"  Versión: {config.API_VERSION}")
    print()
    print("Para importar en n8n:")
    print("  1. Abre la UI: http://localhost:8001/ui → tab n8n")
    print("  2. Haz clic en 'Cargar JSON' → 'Copiar'")
    print("  3. En n8n: menú ⋮ → Import from JSON (Ctrl+Shift+V)")


if __name__ == "__main__":
    main()
