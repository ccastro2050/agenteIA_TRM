"""
tools.py — Herramientas del Agente de Analítica
================================================
Proyecto agente_IA_TRM · USB Medellín

Tres grupos de herramientas especializadas:

  TOOLS_TRM   → Tipo de cambio dólar/peso colombiano
    obtener_trm_actual()            tasa más reciente del CSV
    analizar_historico_trm(meses)   tendencia y estadísticas históricas

  TOOLS_DATOS → Comercio exterior Colombia 2024
    consultar_balanza_comercial()    exportaciones vs importaciones mensuales
    analizar_sectores_exportacion()  estructura sectorial de exportaciones

  TOOLS_RAG   → Documentos DANE (índice vectorial en pgvector)
    buscar_documentos_dane(query, k) búsqueda semántica en reportes DANE
    listar_reportes_dane()           catálogo de documentos disponibles

Prerequisito para TOOLS_RAG: ejecutar preparar_base.py al menos una vez.
"""

import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config
from langchain_core.tools import tool
from vectorstore_factory import crear_embeddings, cargar_vectorstore


# ===========================================================================
# GRUPO 1 — Herramientas TRM (Tipo de cambio)
# ===========================================================================

@tool
def obtener_trm_actual() -> str:
    """
    Retorna la tasa de cambio representativa del mercado (TRM) más reciente
    del año 2024, junto con la variación respecto al mes anterior.

    No requiere parámetros.

    Ejemplo de respuesta:
        {"mes": "Diciembre", "año": 2024, "trm": 4359.0,
         "variacion_pct": 2.45, "interpretacion": "El dólar subió 2.45% en Diciembre"}
    """
    try:
        import pandas as pd
        ruta = config.DATOS_DIR / "trm_2024.csv"
        df   = pd.read_csv(ruta)
        ult  = df.iloc[-1]
        ant  = df.iloc[-2]

        direccion = "subió" if float(ult["variacion_pct"]) > 0 else "bajó"
        interpretacion = (
            f"El dólar {direccion} {abs(float(ult['variacion_pct'])):.2f}% "
            f"en {ult['nombre_mes']} respecto a {ant['nombre_mes']}."
        )

        return json.dumps({
            "mes":              ult["nombre_mes"],
            "año":              int(ult["año"]),
            "trm":              float(ult["trm"]),
            "variacion_pct":    round(float(ult["variacion_pct"]), 2),
            "trm_mes_anterior": float(ant["trm"]),
            "interpretacion":   interpretacion,
            "nota":             "Fuente: Banco de la República · datos/trm_2024.csv",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"No se pudo leer trm_2024.csv: {str(e)}"},
                          ensure_ascii=False)


@tool
def analizar_historico_trm(meses: int = 6) -> str:
    """
    Analiza la tendencia histórica del TRM durante los últimos N meses de 2024.
    Calcula mínimo, máximo, promedio y variación acumulada del período.

    Parámetros:
        meses: número de meses a analizar (1-12, default 6)

    Ejemplo de uso:
        analizar_historico_trm(meses=3)    → análisis del último trimestre
        analizar_historico_trm(meses=12)   → análisis del año completo
    """
    try:
        import pandas as pd
        meses = max(1, min(int(meses), 12))
        ruta  = config.DATOS_DIR / "trm_2024.csv"
        df    = pd.read_csv(ruta).tail(meses)

        trm_min    = float(df["trm"].min())
        trm_max    = float(df["trm"].max())
        trm_prom   = float(df["trm"].mean())
        trm_inicio = float(df.iloc[0]["trm"])
        trm_fin    = float(df.iloc[-1]["trm"])
        variacion  = round((trm_fin - trm_inicio) / trm_inicio * 100, 2)

        tendencia = "alcista" if variacion > 0 else "bajista"
        serie = [
            {"mes": row["nombre_mes"], "trm": float(row["trm"]),
             "variacion_pct": round(float(row["variacion_pct"]), 2)}
            for _, row in df.iterrows()
        ]

        return json.dumps({
            "periodo":                f"últimos {meses} meses de 2024",
            "desde":                  df.iloc[0]["nombre_mes"],
            "hasta":                  df.iloc[-1]["nombre_mes"],
            "trm_minimo":             trm_min,
            "trm_maximo":             trm_max,
            "trm_promedio":           round(trm_prom, 2),
            "variacion_acumulada_pct": variacion,
            "tendencia":              tendencia,
            "serie_mensual":          serie,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Error analizando TRM: {str(e)}"},
                          ensure_ascii=False)


# ===========================================================================
# GRUPO 2 — Herramientas Datos (Comercio exterior)
# ===========================================================================

@tool
def consultar_balanza_comercial() -> str:
    """
    Retorna la balanza comercial mensual de Colombia en 2024:
    exportaciones, importaciones y saldo (exportaciones - importaciones).

    Un saldo negativo (déficit comercial) significa que Colombia importa
    más de lo que exporta. Un saldo positivo sería superávit.

    No requiere parámetros.
    """
    try:
        import pandas as pd
        ruta = config.DATOS_DIR / "comercio_exterior_2024.csv"
        df   = pd.read_csv(ruta)

        total_exp   = float(df["exportaciones_usd_mill"].sum())
        total_imp   = float(df["importaciones_usd_mill"].sum())
        balanza_tot = round(total_exp - total_imp, 1)
        tipo        = "superávit" if balanza_tot >= 0 else "déficit"

        mes_mayor_exp = df.loc[df["exportaciones_usd_mill"].idxmax()]
        mes_mayor_imp = df.loc[df["importaciones_usd_mill"].idxmax()]

        serie = [
            {
                "mes":           row["nombre_mes"],
                "exportaciones": float(row["exportaciones_usd_mill"]),
                "importaciones": float(row["importaciones_usd_mill"]),
                "balanza":       float(row["balanza_comercial"]),
            }
            for _, row in df.iterrows()
        ]

        return json.dumps({
            "año":                     2024,
            "total_exportaciones_usd": round(total_exp, 1),
            "total_importaciones_usd": round(total_imp, 1),
            "balanza_anual_usd":       balanza_tot,
            "tipo_balanza":            tipo,
            "mes_mayor_exportacion":   mes_mayor_exp["nombre_mes"],
            "mes_mayor_importacion":   mes_mayor_imp["nombre_mes"],
            "serie_mensual":           serie,
            "nota":                    "Valores en millones de dólares USD · Fuente DANE/DIAN",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps(
            {"error": f"Error leyendo comercio_exterior_2024.csv: {str(e)}"},
            ensure_ascii=False)


@tool
def analizar_sectores_exportacion() -> str:
    """
    Retorna la estructura de las exportaciones colombianas por sector económico
    en 2024: valor, participación porcentual y variación anual de cada sector.

    Identifica los principales productos de exportación y la diversificación
    de la canasta exportadora colombiana.

    No requiere parámetros.
    """
    try:
        import pandas as pd
        ruta = config.DATOS_DIR / "exportaciones_sectores_2024.csv"
        df   = pd.read_csv(ruta).sort_values("participacion_pct", ascending=False)

        total = float(df["valor_usd_mill"].sum())

        top3 = df.head(3)[["sector", "participacion_pct", "valor_usd_mill"]].to_dict("records")
        sectores_crecimiento = df[df["variacion_anual_pct"] > 0].sort_values(
            "variacion_anual_pct", ascending=False
        )[["sector", "variacion_anual_pct"]].head(3).to_dict("records")

        sectores = [
            {
                "sector":              row["sector"],
                "valor_usd_mill":      float(row["valor_usd_mill"]),
                "participacion_pct":   float(row["participacion_pct"]),
                "variacion_anual_pct": float(row["variacion_anual_pct"]),
            }
            for _, row in df.iterrows()
        ]

        return json.dumps({
            "año":                       2024,
            "total_exportaciones_usd":   round(total, 1),
            "sectores_por_participacion": sectores,
            "top_3_sectores":            top3,
            "sectores_con_mayor_crecimiento": sectores_crecimiento,
            "nota": "Valores en millones USD · Participación sobre total exportaciones",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps(
            {"error": f"Error leyendo exportaciones_sectores_2024.csv: {str(e)}"},
            ensure_ascii=False)


# ===========================================================================
# GRUPO 3 — Herramientas RAG (documentos DANE en pgvector)
# ===========================================================================

_vectorstore_rag = None


def _obtener_vectorstore():
    """
    Carga el índice vectorial de pgvector.
    Se inicializa solo una vez (lazy loading).
    Prerequisito: haber ejecutado preparar_base.py al menos una vez.
    """
    global _vectorstore_rag
    if _vectorstore_rag is None:
        embeddings = crear_embeddings(config)
        _vectorstore_rag = cargar_vectorstore(embeddings, config)
    return _vectorstore_rag


@tool
def buscar_documentos_dane(query: str, k: int = 4) -> str:
    """
    Busca los fragmentos más relevantes en los reportes del DANE
    usando búsqueda semántica (embeddings vectoriales en pgvector).

    Documentos disponibles: desempleo, IPC/inflación, PIB y censo de población.

    Parámetros:
        query: pregunta o términos a buscar (en español)
        k:     número de fragmentos a recuperar (default 4, máximo 8)

    Prerequisito: haber ejecutado python preparar_base.py al menos una vez.
    """
    k = max(1, min(int(k), 8))
    try:
        vs         = _obtener_vectorstore()
        resultados = vs.similarity_search_with_score(query, k=k)

        fragmentos = []
        for doc, distancia in resultados:
            dist_py    = float(distancia)
            relevancia = round(max(0.0, 1.0 - dist_py / 2.0), 3)
            fragmentos.append({
                "texto":      doc.page_content,
                "fuente":     doc.metadata.get("fuente", ""),
                "titulo":     doc.metadata.get("titulo", ""),
                "relevancia": relevancia,
            })

        return json.dumps({
            "query":      query,
            "k":          k,
            "fragmentos": fragmentos,
            "total":      len(fragmentos),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps(
            {"error": f"Error en búsqueda semántica: {str(e)}"},
            ensure_ascii=False)


@tool
def listar_reportes_dane() -> str:
    """
    Lista los reportes del DANE disponibles en el índice vectorial.
    Muestra tema, período y términos clave de cada documento.

    Úsala para saber qué información está disponible antes de buscar.
    No requiere parámetros.
    """
    catalogo = [
        {
            "nombre":  "boletin_desempleo_2024",
            "titulo":  "Boletín Técnico — Mercado Laboral Colombia Q3 2024",
            "tema":    "Desempleo y mercado laboral",
            "periodo": "Julio–Septiembre 2024",
            "datos_clave": ["Desempleo nacional 10,8%", "Chocó 20,1%", "Informalidad 56,3%"],
        },
        {
            "nombre":  "boletin_ipc_2024",
            "titulo":  "Boletín Técnico — IPC Diciembre 2024",
            "tema":    "Inflación y precios al consumidor",
            "periodo": "Diciembre 2024 (resultado anual)",
            "datos_clave": ["IPC 2024: 5,17%", "Pico 2022: 13,12%", "IPC por ciudades"],
        },
        {
            "nombre":  "cuentas_nacionales_pib_2024",
            "titulo":  "Cuentas Nacionales — PIB Colombia 2024",
            "tema":    "Crecimiento económico",
            "periodo": "Año 2024",
            "datos_clave": ["PIB 2024: +1,8%", "Rebote 2021: +10,7%", "Caída COVID 2020: -6,8%"],
        },
        {
            "nombre":  "censo_poblacion_2023",
            "titulo":  "Censo Nacional de Población y Vivienda — Colombia 2023",
            "tema":    "Demografía y población",
            "periodo": "2023",
            "datos_clave": ["51,5M habitantes", "Bogotá 8,7M", "Urbanización 81,1%"],
        },
    ]
    return json.dumps({
        "documentos_disponibles": catalogo,
        "total": len(catalogo),
        "instrucciones": (
            "Usa buscar_documentos_dane(query) para buscar en estos documentos. "
            "El índice debe estar creado (python preparar_base.py)."
        ),
    }, ensure_ascii=False, indent=2)


# ===========================================================================
# Exportar grupos de herramientas
# ===========================================================================

TOOLS_TRM   = [obtener_trm_actual, analizar_historico_trm]
TOOLS_DATOS = [consultar_balanza_comercial, analizar_sectores_exportacion]
TOOLS_RAG   = [buscar_documentos_dane, listar_reportes_dane]
TOOLS_TODOS = TOOLS_TRM + TOOLS_DATOS + TOOLS_RAG
