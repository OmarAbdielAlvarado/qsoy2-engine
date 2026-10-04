from fastapi import FastAPI
from fastapi import FastAPI, Query, HTTPException, Request
from app.ocean_engine import calcular_ocean, buscar_redes_sociales
from app.ocean_engine import calcular_ocean, buscar_redes_sociales
from app.rutas_engine import calcular_ruta_optima


# Diccionario oficial INE
ESTADOS_MAP = {
    1: "Aguascalientes", 2: "Baja California", 3: "Baja California Sur",
    4: "Campeche", 5: "Coahuila", 6: "Colima", 7: "Chiapas", 8: "Chihuahua",
    9: "Ciudad de México", 10: "Durango", 11: "Guanajuato", 12: "Guerrero",
    13: "Hidalgo", 14: "Jalisco", 15: "Estado de México", 16: "Michoacán",
    17: "Morelos", 18: "Nayarit", 19: "Nuevo León", 20: "Oaxaca",
    21: "Puebla", 22: "Querétaro", 23: "Quintana Roo", 24: "San Luis Potosí",
    25: "Sinaloa", 26: "Sonora", 27: "Tabasco", 28: "Tamaulipas",
    29: "Tlaxcala", 30: "Veracruz", 31: "Yucatán", 32: "Zacatecas"
}

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from typing import Optional
import os
import json
import logging
from datetime import datetime

from clickhouse_connect import get_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN - ClickHouse (conexión diferida)
# ============================================================
CH_HOST = "localhost"  # Con network_mode: host, localhost es el host
CH_PORT = 8123
CH_USER = "default"
CH_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD","")
CH_DATABASE = "qsoy"

ch_client = None

def get_ch_client():
    global ch_client
    if ch_client is None:
        try:
            ch_client = get_client(
                host=CH_HOST,
                port=CH_PORT,
                username=CH_USER,
                password=CH_PASSWORD,
                database=CH_DATABASE
            )
            logger.info(f"✅ Conectado a ClickHouse: {CH_HOST}:{CH_PORT}/{CH_DATABASE}")
        except Exception as e:
            logger.error(f"❌ Error conectando a ClickHouse: {e}")
            ch_client = None
            raise
    return ch_client

def q(sql):
    client = get_ch_client()
    if client is None:
        raise Exception("ClickHouse no disponible")
    return client.query(sql).result_rows or []

def q1(sql):
    r = q(sql)
    return r[0][0] if r else 0

def safe(s):
    if not s:
        return ""
    return str(s).replace("'", "").replace(";", "").replace("--", "")

# ============================================================
# APLICACIÓN FastAPI
# ============================================================
app = FastAPI(title="QSoy2 API v3.1", description="API datos electorales", version="3.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')

ESTADOS = {
    1: "Aguascalientes", 2: "BC", 3: "BCS", 4: "Campeche", 5: "Coahuila",
    6: "Colima", 7: "Chiapas", 8: "Chihuahua", 9: "CDMX", 10: "Durango",
    11: "Guanajuato", 12: "Guerrero", 13: "Hidalgo", 14: "Jalisco",
    15: "Mexico", 16: "Michoacan", 17: "Morelos", 18: "Nayarit",
    19: "Nuevo Leon", 20: "Oaxaca", 21: "Puebla", 22: "Queretaro",
    23: "QRoo", 24: "SLP", 25: "Sinaloa", 26: "Sonora", 27: "Tabasco",
    28: "Tamaulipas", 29: "Tlaxcala", 30: "Veracruz", 31: "Yucatan",
    32: "Zacatecas"
}

PCOLORS = {
    "MORENA": "#AE1638", "PAN": "#0056A3", "PRI": "#009846",
    "PRD": "#F5A623", "MC": "#FF6B00", "PVEM": "#5CB85C",
    "PT": "#D4213D", "PAN_PRI_PRD": "#6B4C9A", "VA_POR_MEXICO": "#0056A3",
    "JUNTOS_HACEMOS_HISTORIA": "#AE1638", "NA": "#666666",
    "PES": "#E67E22", "INDEPENDIENTE": "#95A5A6"
}

def pcolor(p):
    if not p:
        return "#999"
    for k, v in PCOLORS.items():
        if k.upper() in (p or "").upper():
            return v
    return "#7F8C8D"

def votante_row(r):
    return {
        "cve": r[0], "edad": r[1], "nombre": r[2], "paterno": r[3], "materno": r[4],
        "fecnac": r[5], "sexo": r[6], "calle": r[7], "int": r[8], "ext": r[9],
        "colonia": r[10], "cp": r[11], "e": r[12], "d": r[13], "m": r[14],
        "s": r[15], "l": r[16], "mza": r[17], "consec": r[18], "cred": r[19],
        "folio": r[20], "nac": r[21], "curp": r[22], "latitud": r[23],
        "longitud": r[24], "dir_limpia": r[25], "geo_metodo": r[26],
        "geo": bool(r[23] and r[24] and r[23] != 0),
        "estado_nombre": ESTADOS.get(int(r[12]), "?")
    }

# ============================================================
# HEALTH CHECK (con captura de error)
# ============================================================
@app.get("/health")
async def health():
    try:
        q("SELECT 1")
        return {"status": "healthy", "database": "ClickHouse", "connected": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "connected": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        )

@app.get("/")
async def root():
    idx = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.isfile(idx):
        with open(idx, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    return JSONResponse(content={"message": "QSoy2 API v3.1", "docs": "/docs"})

@app.get("/candidatos.js")
async def candidatos_js():
    p = os.path.join(FRONTEND_DIR, 'candidatos.js')
    if os.path.isfile(p):
        return FileResponse(p, media_type="application/javascript")
    return JSONResponse(status_code=404, content={"error": "No encontrado"})

# ============================================================
# ENDPOINTS BÁSICOS (minimalistas)
# ============================================================
@app.get("/status")
async def status():
    try:
        total = q1("SELECT count() FROM votantes_csv")
        return {"total_registros": total, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/estados")
async def estados():
    rows = q("SELECT e, count() FROM votantes_csv GROUP BY e ORDER BY e")
    return {"estados": [{"codigo": r[0], "nombre": ESTADOS.get(int(r[0]), "?"), "total": r[1]} for r in rows]}

@app.get("/votantes/estadisticas")
async def estadisticas():
    try:
        total = q1("SELECT count() FROM votantes_csv")
        return {"total_votantes": total, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================
# ENDPOINT DE BÚSQUEDA (ClickHouse con Skip Indexes)
# ============================================================
@app.get("/votantes/buscar")
async def buscar_votantes(
    nombre: Optional[str] = None,
    paterno: Optional[str] = None,
    materno: Optional[str] = None,
    cve: Optional[str] = None,
    curp: Optional[str] = None,
    seccion: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    Busca votantes en ClickHouse. 
    Usa ILIKE para texto (aprovecha los índices ngrambf_v1) y = para claves exactas.
    """
    conditions = []
    params = {}
    
    if nombre:
        conditions.append("nombre ILIKE %(nombre)s")
        params["nombre"] = f"%{nombre}%"
    if paterno:
        conditions.append("paterno ILIKE %(paterno)s")
        params["paterno"] = f"%{paterno}%"
    if materno:
        conditions.append("materno ILIKE %(materno)s")
        params["materno"] = f"%{materno}%"
    if cve:
        conditions.append("cve = %(cve)s")
        params["cve"] = cve
    if curp:
        conditions.append("curp = %(curp)s")
        params["curp"] = curp
    if seccion:
        conditions.append("s = %(seccion)s")
        params["seccion"] = seccion
        
    if not conditions:
        raise HTTPException(400, "Debe proporcionar al menos un criterio de búsqueda")
        
    try:
        where_clause = " AND ".join(conditions)
        
        sql = f"""
        SELECT cve, edad, nombre, paterno, materno, sexo, calle, ext, colonia, cp, e, m, s, curp
        FROM votantes_csv
        WHERE {where_clause}
        LIMIT %(limit)s
        """
        
        client = get_ch_client()
        result = client.query(sql, parameters={**params, "limit": limit})
        columns = ["cve", "edad", "nombre", "paterno", "materno", "sexo", "calle", "ext", "colonia", "cp", "e", "m", "s", "curp"]
        votantes = [dict(zip(columns, row)) for row in result.result_rows]
        
        return {"resultados": votantes, "total": len(votantes)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))



# ============================================================
# ENDPOINTS REQUERIDOS POR EL FRONTEND (BÚSQUEDA Y PADRÓN)
# ============================================================
@app.get("/votantes/search/name")
async def search_name(nombre: str = "", paterno: str = "", materno: str = "", estado: str = "", municipio: str = "", limit: int = 50, page: int = 1):
    conditions = []
    params = {'limit': limit, 'offset': (page - 1) * limit}
    if nombre: conditions.append("nombre ILIKE %(nombre)s"); params["nombre"] = f"%{nombre}%"
    if paterno: conditions.append("paterno ILIKE %(paterno)s"); params["paterno"] = f"%{paterno}%"
    if materno: conditions.append("materno ILIKE %(materno)s"); params["materno"] = f"%{materno}%"
    if estado: conditions.append("e = %(estado)s OR e = %(estado_nz)s"); params["estado_nz"] = estado.lstrip("0") or "0"; params["estado"] = estado
    if municipio: conditions.append("m = %(municipio)s OR m = %(municipio_nz)s"); params["municipio_nz"] = municipio.lstrip("0") or "0"; params["municipio"] = municipio
    if not conditions: 
        raise HTTPException(400, "Debe proporcionar al menos un criterio")
    try:
        where = " AND ".join(conditions)
        sql = f"SELECT cve, nombre, paterno, materno, curp, e, m, s, calle, ext, colonia, cp, sexo, edad FROM votantes_csv WHERE {where} LIMIT %(limit)s OFFSET %(offset)s"
        client = get_ch_client()
        res = client.query(sql, parameters=params)
        cols = ["cve","nombre","paterno","materno","curp","e","m","s","calle","ext","colonia","cp","sexo","edad"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows], "total_in_range": len(res.result_rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/votantes/search/curp")
async def search_curp(curp: str):
    try:
        sql = "SELECT * FROM votantes_csv WHERE curp = %(curp)s LIMIT 1"
        client = get_ch_client()
        res = client.query(sql, parameters={'curp': curp})
        if not res.result_rows: raise HTTPException(404, "CURP no encontrado")
        # Fix: res.column_names ya es una lista de strings, no tuples
        cols = list(res.column_names)
        if 'int_' in cols:
            idx = cols.index('int_')
            cols[idx] = 'int'
        return {"results": [dict(zip(cols, res.result_rows[0]))]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/votantes/search/manzana")
async def search_manzana(e: str, m: str, s: str, mza: str, limit: int = 100):
    try:
        sql = "SELECT cve, nombre, paterno, materno, curp, calle, ext, colonia, cp, sexo, edad FROM votantes_csv WHERE e = %(e)s AND m = %(m)s AND s = %(s)s AND mza = %(mza)s LIMIT %(limit)s"
        client = get_ch_client()
        res = client.query(sql, parameters={'e': e, 'm': m, 's': s, 'mza': mza, 'limit': limit})
        cols = ["cve","nombre","paterno","materno","curp","calle","ext","colonia","cp","sexo","edad"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows], "total": len(res.result_rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/votantes/search/address")
async def search_address(estado: str = "", municipio: str = "", colonia: str = "", calle: str = "", seccion: str = "", limit: int = 50, page: int = 1, solo_geo: bool = False):
    try:
        conditions = []
        params = {'limit': limit, 'offset': (page - 1) * limit}
        if estado: conditions.append("e = %(estado)s OR e = %(estado_nz)s"); params["estado_nz"] = estado.lstrip("0") or "0"; params["estado"] = estado
        if municipio: conditions.append("m = %(municipio)s OR m = %(municipio_nz)s"); params["municipio_nz"] = municipio.lstrip("0") or "0"; params["municipio"] = municipio
        if colonia: conditions.append("colonia ILIKE %(colonia)s"); params["colonia"] = f"%{colonia}%"
        if calle: conditions.append("calle ILIKE %(calle)s"); params["calle"] = f"%{calle}%"
        if seccion: conditions.append("s = %(seccion)s"); params["seccion"] = seccion
        if solo_geo: conditions.append("latitud IS NOT NULL")
        if not conditions: raise HTTPException(400, "Debe proporcionar al menos un criterio")
        
        where = " AND ".join(conditions)
        sql = f"SELECT cve, nombre, paterno, materno, curp, e, m, s, calle, ext, colonia, cp, latitud, longitud FROM votantes_csv WHERE {where} LIMIT %(limit)s OFFSET %(offset)s"
        client = get_ch_client()
        res = client.query(sql, parameters=params)
        cols = ["cve","nombre","paterno","materno","curp","e","m","s","calle","ext","colonia","cp","latitud","longitud"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows], "total_in_range": len(res.result_rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/votantes/search/relatives/{curp}")
async def search_relatives(curp: str):
    try:
        client = get_ch_client()
        # 1. Obtener datos de la persona
        base_sql = "SELECT paterno, materno, e, s, calle FROM votantes_csv WHERE curp = %(curp)s LIMIT 1"
        base_res = client.query(base_sql, parameters={'curp': curp}).result_rows
        if not base_res: raise HTTPException(404, "CURP no encontrado")
        
        paterno, materno, e, s, calle = base_res[0]
        # 2. Buscar familiares: mismo apellido y misma sección/calle
        rel_sql = """
        SELECT cve, nombre, paterno, materno, curp, calle, ext, colonia, edad, sexo 
        FROM votantes_csv 
        WHERE paterno = %(paterno)s AND materno = %(materno)s AND e = %(e)s AND s = %(s)s AND curp != %(curp)s
        LIMIT 50
        """
        res = client.query(rel_sql, parameters={'paterno': paterno, 'materno': materno, 'e': e, 's': s, 'curp': curp})
        cols = ["cve","nombre","paterno","materno","curp","calle","ext","colonia","edad","sexo"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows], "total": len(res.result_rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/votantes/search/address_neighbors/{curp}")
async def search_neighbors(curp: str):
    try:
        client = get_ch_client()
        base_sql = "SELECT e, s, calle FROM votantes_csv WHERE curp = %(curp)s LIMIT 1"
        base_res = client.query(base_sql, parameters={'curp': curp}).result_rows
        if not base_res: raise HTTPException(404, "CURP no encontrado")
        
        e, s, calle = base_res[0]
        neigh_sql = """
        SELECT cve, nombre, paterno, materno, curp, ext, colonia, edad, sexo, latitud, longitud 
        FROM votantes_csv 
        WHERE e = %(e)s AND s = %(s)s AND calle = %(calle)s AND curp != %(curp)s
        LIMIT 50
        """
        res = client.query(neigh_sql, parameters={'e': e, 's': s, 'calle': calle, 'curp': curp})
        cols = ["cve","nombre","paterno","materno","curp","ext","colonia","edad","sexo","latitud","longitud"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows], "total": len(res.result_rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/votantes/search/text")
async def search_text(q: str, estado: str = "", limit: int = 50):
    try:
        conditions = ["(nombre ILIKE %(q)s OR paterno ILIKE %(q)s OR curp ILIKE %(q)s OR calle ILIKE %(q)s)"]
        params = {'q': f"%{q}%", 'limit': limit}
        if estado:
            conditions.append("e = %(estado)s OR e = %(estado_nz)s"); params["estado_nz"] = estado.lstrip("0") or "0"
            params["estado"] = estado
        where = " AND ".join(conditions)
        sql = f"SELECT cve, nombre, paterno, materno, curp, e, m, s, calle, ext, colonia FROM votantes_csv WHERE {where} LIMIT %(limit)s"
        client = get_ch_client()
        res = client.query(sql, parameters=params)
        cols = ["cve","nombre","paterno","materno","curp","e","m","s","calle","ext","colonia"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows], "total": len(res.result_rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/municipios/{estado}")
async def get_municipios(estado: int):
    try:
        sql = "SELECT municipio, nombre FROM cat_municipios WHERE entidad = %(estado)s ORDER BY nombre"
        client = get_ch_client()
        res = client.query(sql, parameters={'estado': estado})
        return {"municipios": [{"value": r[0], "text": r[1]} for r in res.result_rows]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/status/detail")
async def status_detail():
    try:
        total = q1("SELECT count() FROM votantes_csv")
        geo = q1("SELECT count() FROM votantes_csv WHERE latitud IS NOT NULL")
        return {
            "total_votantes": total,
            "total_geo": geo,
            "pct_geo": round((geo/total*100), 2) if total > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))



@app.get("/votantes/search/address_domicile/{curp}")
async def search_domicile(curp: str):
    """Busca personas que viven EXACTAMENTE en el mismo domicilio (misma calle, ext, int, colonia)"""
    try:
        client = get_ch_client()
        base_sql = "SELECT e, m, s, calle, ext, int_, colonia, cp FROM votantes_csv WHERE curp = %(curp)s LIMIT 1"
        base_res = client.query(base_sql, parameters={'curp': curp}).result_rows
        if not base_res: raise HTTPException(404, "CURP no encontrado")
        
        e, m, s, calle, ext, int_, colonia, cp = base_res[0]
        
        # FIX: Evitar agrupar comunidades enteras con calles genericas (SIN NOMBRE, S/N, 0)
        calle_invalida = calle.upper() in ['C SIN NOMBRE', 'SIN NOMBRE', 'CALLE SIN NOMBRE', '0', ''] or ext.upper() in ['S/N', '0', '']
        
        if calle_invalida:
            return {"results": [], "total": 0, "message": "Domicilio genérico (Sin Nombre/S/N). No se puede determinar con precisión quién más vive aquí."}
            
        dom_sql = """
        SELECT cve, nombre, paterno, materno, curp, ext, int_ AS int, colonia, cp, edad, sexo 
        FROM votantes_csv 
        WHERE e = %(e)s AND m = %(m)s AND s = %(s)s AND calle = %(calle)s 
          AND ext = %(ext)s AND int_ = %(int_)s AND colonia = %(colonia)s 
          AND curp != %(curp)s
        LIMIT 50
        """
        res = client.query(dom_sql, parameters={
            'e': e, 'm': m, 's': s, 'calle': calle, 'ext': ext, 'int_': int_, 'colonia': colonia, 'curp': curp
        })
        cols = ["cve","nombre","paterno","materno","curp","ext","int","colonia","cp","edad","sexo"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows], "total": len(res.result_rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

# ============================================================
# ENDPOINTS ANALÍTICOS AVANZADOS (HEATMAP, CANDIDATOS, HISTÓRICOS, OCEAN)
# ============================================================
@app.get("/votantes/heatmap")
async def heatmap(estado: str = "", municipio: str = ""):
    """Agrega votantes por sección para dibujar mapa de calor en el frontend"""
    try:
        conditions = ["latitud IS NOT NULL", "longitud IS NOT NULL"]
        params = {}
        if estado:
            conditions.append("e = %(estado)s OR e = %(estado_nz)s"); params["estado_nz"] = estado.lstrip("0") or "0"
            params["estado"] = estado
        if municipio:
            conditions.append("m = %(municipio)s OR m = %(municipio_nz)s"); params["municipio_nz"] = municipio.lstrip("0") or "0"
            params["municipio"] = municipio
            
        where = " AND ".join(conditions)
        # ClickHouse es rapidísimo haciendo GROUP BY
        sql = f"""
        SELECT e, s, count() as total, 
               avg(latitud) as lat, avg(longitud) as lon,
               countIf(sexo='M') as mujeres, countIf(sexo='H') as hombres
        FROM votantes_csv 
        WHERE {where}
        GROUP BY e, s
        HAVING lat > 15 AND lat < 33 AND lon > -118 AND lon < -86
        LIMIT 10000
        """
        client = get_ch_client()
        res = client.query(sql, parameters=params)
        data = [{"e": r[0], "s": r[1], "total": r[2], "lat": r[3], "lon": r[4], "mujeres": r[5], "hombres": r[6]} for r in res.result_rows]
        return {"results": data, "total_secciones": len(data)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/candidatos/filtros")
async def candidatos_filtros():
    """Devuelve listas únicas para los dropdowns del frontend"""
    try:
        client = get_ch_client()
        anios = client.query("SELECT DISTINCT anio FROM candidaturas ORDER BY anio DESC").result_rows
        tipos = client.query("SELECT DISTINCT tipo_eleccion FROM candidaturas WHERE tipo_eleccion != ''").result_rows
        partidos = client.query("SELECT DISTINCT partido FROM candidaturas WHERE partido != '' ORDER BY partido").result_rows
        estados = client.query("SELECT DISTINCT estado FROM candidaturas ORDER BY estado").result_rows
        return {
            "anios": [r[0] for r in anios],
            "tipos": [r[0] for r in tipos],
            "partidos": [r[0] for r in partidos],
            "estados": [{"valor": r[0], "nombre": ESTADOS.get(int(r[0]), "?")} for r in estados]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/resultados/historicos")
async def get_historicos(estado: str = Query(...), anio: Optional[int] = None):
    try:
        # Usamos resultados_electorales porque tiene municipio y candidato
        sql = "SELECT anio, tipo_eleccion, toString(estado) AS estado, municipio, partido, candidato, votos FROM resultados_historicos WHERE toString(estado) = %(estado)s"
        params = {'estado': estado}
        if anio:
            sql += " AND anio = %(anio)s"
            params['anio'] = anio
        sql += " ORDER BY votos DESC LIMIT 1000"
        
        client = get_ch_client()
        res = client.query(sql, parameters=params)
        cols = ["anio", "tipo_eleccion", "estado", "municipio", "partido", "candidato", "votos"]
        return {"resultados": [dict(zip(cols, r)) for r in res.result_rows]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/ocean/segmentacion")
async def ocean_segmentacion(estado: str = "", municipio: str = ""):
    """Obtiene perfiles psicológicos OCEAN por zona geográfica"""
    try:
        conditions = []
        params = {}
        if estado: conditions.append("estado = %(estado)s"); params["estado"] = estado
        if municipio: conditions.append("municipio = %(municipio)s"); params["municipio"] = municipio
        
        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
        SELECT municipio, perfil_dominante, o_apertura_prom, c_responsabilidad_prom, 
               e_extroversion_prom, a_amabilidad_prom, n_neuroticismo_prom,
               partido_lider, pct_intencion
        FROM ocean_segmentacion
        WHERE {where}
        LIMIT 100
        """
        client = get_ch_client()
        res = client.query(sql, parameters=params)
        data = [{
            "municipio": r[0], "perfil": r[1], "o": round(r[2],1) if r[2] else 0, "c": round(r[3],1) if r[3] else 0,
            "e": round(r[4],1) if r[4] else 0, "a": round(r[5],1) if r[5] else 0, "n": round(r[6],1) if r[6] else 0,
            "partido_lider": r[7], "intencion": r[8]
        } for r in res.result_rows]
        return {"results": data, "total": len(data)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================
# ENDPOINTS FALTANTES DEL FRONTEND (ENCUESTAS, HISTORIAL, AUTOCOMPLETADO)
# ============================================================
@app.get("/candidaturas/por_curp")
async def candidaturas_por_curp(curp: str):
    """Obtiene el historial electoral de un candidato por su CURP"""
    try:
        client = get_ch_client()
        sql = "SELECT anio, tipo, partido, partido FROM candidaturas_padron WHERE curp = %(curp)s ORDER BY anio DESC"
        res = client.query(sql, parameters={'curp': curp})
        return [{"anio": r[0], "tipo": r[1], "partido": r[2], "partido": r[3]} for r in res.result_rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/encuestas")
async def get_encuestas(estado: str = ""):
    """Obtiene encuestas capturadas por estado"""
    try:
        client = get_ch_client()
        sql = "SELECT fecha, partido_preferido, intencion_voto, peso_estadistico FROM encuestas"
        params = {}
        if estado:
            sql += " WHERE estado = %(estado)s"
            params['estado'] = estado
        sql += " ORDER BY fecha DESC LIMIT 100"
        res = client.query(sql, parameters=params)
        data = [{"fecha": str(r[0]), "partido_preferido": r[1], "intencion_voto": r[2], "peso_estadistico": r[3]} for r in res.result_rows]
        return {"encuestas": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/encuestas/stats")
async def get_encuestas_stats(estado: str = ""):
    """Estadísticas de encuestas por estado"""
    try:
        client = get_ch_client()
        where = "WHERE estado = %(estado)s" if estado else ""
        params = {'estado': estado} if estado else {}
        
        total = client.query(f"SELECT count() FROM encuestas {where}", parameters=params).result_rows[0][0]
        validadas = client.query(f"SELECT count() FROM encuestas {where} {'AND' if where else 'WHERE'} validada = 1", parameters=params).result_rows[0][0]
        pp_res = client.query(f"SELECT partido_preferido, count() as n FROM encuestas {where} GROUP BY partido_preferido ORDER BY n DESC", parameters=params).result_rows
        
        return {
            "total": total,
            "validadas": validadas,
            "por_partido": [{"partido": r[0], "n": r[1]} for r in pp_res]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/encuestas/upload")
async def upload_encuesta(data: dict):
    """Recibe datos de encuesta desde el frontend"""
    try:
        client = get_ch_client()
        cols = ['estado', 'encuesta_id', 'fecha', 'seccion', 'colonia', 'calle', 'ext', 'intencion_voto', 'candidato_preferido', 'partido_preferido', 'nivel_seguridad', 'medio_contacto', 'validada', 'lista_nominal_seccion', 'n_encuestados_seccion', 'peso_estadistico', 'sexo_encuestado', 'edad_encuestado']
        row = [
            data.get('estado',''), data.get('encuesta_id',''), data.get('fecha',''), data.get('seccion',''), data.get('colonia',''), 
            data.get('calle',''), data.get('ext',''), data.get('intencion_voto',''), data.get('candidato_preferido',''), 
            data.get('partido_preferido',''), data.get('nivel_seguridad',3), data.get('medio_contacto','whatsapp'), 
            data.get('validada',0), data.get('lista_nominal_seccion',0), data.get('n_encuestados_seccion',0), 
            data.get('peso_estadistico',0.0), data.get('sexo_encuestado',''), data.get('edad_encuestado',0)
        ]
        client.insert('encuestas', [row], column_names=cols)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/calles/{estado}/{municipio}")
async def get_calles(estado: str, municipio: str):
    try:
        client = get_ch_client()
        sql = "SELECT DISTINCT calle FROM votantes_csv WHERE e = %(e)s AND m = %(m)s AND calle != '' LIMIT 100"
        res = client.query(sql, parameters={'e': estado, 'm': municipio})
        return [r[0] for r in res.result_rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/colonias/{estado}/{municipio}")
async def get_colonias(estado: str, municipio: str):
    try:
        client = get_ch_client()
        sql = "SELECT DISTINCT colonia FROM votantes_csv WHERE e = %(e)s AND m = %(m)s AND colonia != '' LIMIT 100"
        res = client.query(sql, parameters={'e': estado, 'm': municipio})
        return [r[0] for r in res.result_rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

# Cartografía (Endpoints Dummy para evitar errores 500 en el frontend si no hay GeoJSON cargado)
@app.get("/stats/segmentacion/")
async def stats_segmentacion(estado: str = ""):
    return {"results": []}

@app.get("/stats/segmentacion/mapa/")
async def stats_segmentacion_mapa(estado: str = ""):
    return {"results": []}

@app.get("/votantes/search/near")
async def search_near(lat: float, lon: float, radio: int = 500, limit: int = 50):
    """Busca votantes cerca de unas coordenadas (usando distancia aproximada)"""
    try:
        client = get_ch_client()
        # Aproximación: 1 grado de latitud = ~111km. Filtramos por un cuadrado rápido.
        delta = radio / 111000.0
        sql = """
        SELECT cve, nombre, paterno, materno, curp, calle, ext, colonia, latitud, longitud 
        FROM votantes_csv 
        WHERE latitud IS NOT NULL AND longitud IS NOT NULL
        AND latitud BETWEEN %(lat_min)s AND %(lat_max)s
        AND longitud BETWEEN %(lon_min)s AND %(lon_max)s
        LIMIT %(limit)s
        """
        res = client.query(sql, parameters={
            'lat_min': lat - delta, 'lat_max': lat + delta,
            'lon_min': lon - delta, 'lon_max': lon + delta,
            'limit': limit
        })
        cols = ["cve","nombre","paterno","materno","curp","calle","ext","colonia","latitud","longitud"]
        return {"results": [dict(zip(cols, r)) for r in res.result_rows]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

# ============================================================
# ENDPOINTS DE CANDIDATOS Y CARTOGRAFIA (DEFINITIVOS)
# ============================================================
@app.get("/candidatos/mapa")
async def candidatos_mapa(estado: str = "", anio: str = "", tipo: str = "", partido: str = "", confianza: str = ""):
    try:
        conditions = []
        params = {}
        if estado and estado != "0": 
            conditions.append("estado = %(estado)s")
            params["estado"] = int(estado)
        if anio: 
            conditions.append("anio = %(anio)s")
            params["anio"] = int(anio) if str(anio).isdigit() else anio
        if tipo: 
            conditions.append("tipo = %(tipo)s")
            params["tipo"] = tipo
        if partido: 
            conditions.append("partido = %(partido)s")
            params["partido"] = partido
        if confianza: 
            conditions.append("confianza = %(confianza)s")
            params["confianza"] = confianza
            
        where = " AND ".join(conditions) if conditions else "1=1"
        geo_filter = "lat > 15 AND lat < 33 AND lon > -118 AND lon < -86"
        
        sql = f"""
        SELECT 
            any(candidato) as label,
            arrayStringConcat(groupArray(DISTINCT partido), ', ') as partido,
            anio,
            tipo,
            estado,
            any(distrito) as distrito,
            any(lat) as lat_final,
            any(lon) as lon_final,
            any('') as domicilio,
            any(0) as seccion,
            any(confianza) as confianza_final,
            any(curp) as curp
        FROM candidaturas_padron
        WHERE {where} AND {geo_filter}
        GROUP BY anio, tipo, estado, candidato
        LIMIT 1000
        """
        
        client = get_ch_client()
        # Usamos named_results para leer por nombre de columna y no por índice
        res = client.query(sql, parameters=params)
        
        data = []
        for row in res.named_results():
            anio_val = row['anio'] if row['anio'] else 2024
            conf_val = str(row['confianza_final']).upper() if row['confianza_final'] else 'MEDIA'
            
            if conf_val == 'MEDIA':
                color = "#808080"
            elif anio_val <= 2018:
                color = "#87CEEB"
            elif anio_val <= 2021:
                color = "#1E90FF"
            else:
                color = "#000080"
                
            data.append({
                "label": row['label'], 
                "partido": row['partido'], 
                "anio": anio_val, 
                "tipo": row['tipo'], 
                "estado": row['estado'], 
                "distrito": row['distrito'],
                "lat": row['lat_final'], 
                "lon": row['lon_final'], 
                "domicilio": row['domicilio'], 
                "seccion": row['seccion'], 
                "confianza": conf_val, 
                "color": color, 
                "curp": row['curp'] or ""
            })
            
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/cartografia/secciones/{estado}")
async def get_secciones_geojson(estado: str):
    from fastapi.responses import FileResponse
    import os
    file_path = f"/home/omar/proyectos/QSoy2/frontend/geojson/seccion_{estado}.geojson"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/json")
    return {"type": "FeatureCollection", "features": []}

@app.get("/cartografia/distritos/{estado}")
async def get_distritos_geojson(estado: str):
    from fastapi.responses import FileResponse
    import os
    file_path = f"/home/omar/proyectos/QSoy2/frontend/geojson/distrito_federal_{estado}.geojson"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/json")
    return {"type": "FeatureCollection", "features": []}

# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002, reload=False)

# --- FIX DEFINITIVO PARA DROPDOWNS ---
ESTADOS_MAP = {
    1: "Aguascalientes", 2: "Baja California", 3: "Baja California Sur",
    4: "Campeche", 5: "Coahuila", 6: "Colima", 7: "Chiapas", 8: "Chihuahua",
    9: "Ciudad de México", 10: "Durango", 11: "Guanajuato", 12: "Guerrero",
    13: "Hidalgo", 14: "Jalisco", 15: "Estado de México", 16: "Michoacán",
    17: "Morelos", 18: "Nayarit", 19: "Nuevo León", 20: "Oaxaca",
    21: "Puebla", 22: "Querétaro", 23: "Quintana Roo", 24: "San Luis Potosí",
    25: "Sinaloa", 26: "Sonora", 27: "Tabasco", 28: "Tamaulipas",
    29: "Tlaxcala", 30: "Veracruz", 31: "Yucatán", 32: "Zacatecas"
}

@app.get("/estados", include_in_schema=False)
async def get_estados_fixed():
    try:
        client = get_ch_client()
        res = client.query("SELECT e, count() FROM votantes_csv GROUP BY e ORDER BY e")
        estados = []
        for row in res.result_rows:
            try:
                codigo = int(row[0])
                nombre = ESTADOS_MAP.get(codigo, f"Desconocido {codigo}")
            except:
                nombre = f"Invalido {row[0]}"
            estados.append({"codigo": codigo, "nombre": nombre, "total": row[1]})
        return estados
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/candidatos/filtros", include_in_schema=False)
async def candidatos_filtros_fixed():
    try:
        client = get_ch_client()
        anios = [r[0] for r in client.query("SELECT DISTINCT anio FROM candidaturas_padron ORDER BY anio DESC").result_rows]
        tipos = [r[0] for r in client.query("SELECT DISTINCT tipo FROM candidaturas_padron ORDER BY tipo").result_rows]
        partidos = [r[0] for r in client.query("SELECT DISTINCT partido FROM candidaturas_padron WHERE partido != '' ORDER BY partido LIMIT 50").result_rows]
        est_res = client.query("SELECT DISTINCT estado FROM candidaturas_padron WHERE estado != 0 ORDER BY estado").result_rows
        estados = [{"valor": int(r[0]), "nombre": ESTADOS_MAP.get(int(r[0]), "Desconocido")} for r in est_res]
        return {"anios": anios, "tipos": tipos, "partidos": partidos, "estados": estados}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# --- ENDPOINTS DE INTELIGENCIA Y PERFILAMIENTO ---
ESTADOS_OCEAN = {
    6: {"Apertura": 78, "Responsabilidad": 65, "Extraversion": 82, "Amabilidad": 60, "Estabilidad": 55},
    15: {"Apertura": 70, "Responsabilidad": 75, "Extraversion": 68, "Amabilidad": 72, "Estabilidad": 60}
}

@app.get("/inteligencia/documentos_publicos")
async def get_docs_publicos():
    return {"documentos": [
        {"tipo": "Georreferenciación Residencial", "fuente": "Fuentes Públicas Autorizadas", "cobertura": "95% de candidatos federales y locales"},
        {"tipo": "Historial de Candidaturas", "fuente": "Registros Públicos Electorales", "cobertura": "2018 - 2025"},
        {"tipo": "Análisis de Redes Sociales", "fuente": "Scraping OSINT", "cobertura": "Facebook, X, Instagram"},
        {"tipo": "Detección de Perfiles Falsos", "fuente": "Algoritmo Propietario QSoy2", "cobertura": "Análisis de Bots y Trolls"}
    ]}

# --- FIX DE DASHBOARD (MAPA DE CALOR) ---
@app.get("/stats/segmentacion/{estado}")
async def get_segmentacion(estado: int, municipio: str = ""):
    try:
        client = get_ch_client()
        # Query optimizada para ClickHouse usando la tabla votantes_csv
        sql = f"""
        SELECT 
            ifNull(s, '0') as seccion,
            count() as total,
            countIf(sexo = 'M') as hombres,
            countIf(sexo = 'H') as mujeres,
            countIf(toUInt32OrZero(edad) >= 18 AND toUInt32OrZero(edad) <= 29) as jovenes,
            countIf(toUInt32OrZero(edad) >= 60) as mayores,
            countIf(latitud IS NOT NULL) as geo,
            any(m) as mun
        FROM votantes_csv 
        WHERE e = '{estado}'
        """
        if municipio:
            sql += f" AND m = '{municipio}'"
        sql += " GROUP BY s ORDER BY total DESC LIMIT 10000"
        
        res = client.query(sql).result_rows
        secciones = []
        for r in res:
            total = r[1]
            if total == 0: continue
            secciones.append({
                "seccion": str(r[0]),
                "total": total,
                "hombres": r[2],
                "mujeres": r[3],
                "jovenes": r[4],
                "mayores": r[5],
                "geo": r[6],
                "municipio": str(r[7] or ''),
                "pct_geo": round((r[6] / total) * 100, 1) if total else 0,
                "pct_mujeres": round((r[3] / total) * 100, 1) if total else 0,
                "pct_jovenes": round((r[4] / total) * 100, 1) if total else 0,
                "pct_mayores": round((r[5] / total) * 100, 1) if total else 0,
                "indice_valor": round((r[6] / total) * 100, 1) if total else 0,
                "edad_prom": 35,
                "colonias": 1
            })
            
        total_votantes = sum(s['total'] for s in secciones)
        return {
            "estado": estado,
            "municipio": municipio,
            "total_votantes": total_votantes,
            "total_secciones": len(secciones),
            "secciones": secciones
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))




@app.get("/inteligencia/perfil/{curp}")
async def inteligencia_perfil(curp: str):
    import clickhouse_connect
    client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''))
    try:
        # 1. Buscar en candidatos
        res = client.query(f"SELECT candidato, partido, estado, anio FROM qsoy.candidaturas WHERE candidato LIKE '%{curp}%' LIMIT 1").result_rows
        if not res:
            res = client.query(f"SELECT nombre, paterno, materno, e FROM qsoy.votantes_csv WHERE curp = '{curp}' LIMIT 1").result_rows
            if not res:
                return {"error": "CURP no encontrado en el padrón ni en candidatos."}
            nombre = f"{res[0][0]} {res[0][1]} {res[0][2]}"
            partido = "Ciudadano"
            estado = res[0][3]
            anio = 2024
        else:
            nombre = res[0][0]
            partido = res[0][1]
            estado = res[0][2]
            anio = res[0][3]
            
        # 2. Calcular OCEAN
        perfil = calcular_ocean(nombre, partido, estado, anio)
        redes = buscar_redes_sociales(nombre)
        
        # 3. Buscar deserciones políticas
        deser = client.query(f"SELECT anios, partidos FROM qsoy.deserciones_politicas WHERE candidato = '{nombre}'").result_rows
        desercion = None
        if deser:
            desercion = {"anios": deser[0][0], "partidos": deser[0][1]}
        
        return {
            "nombre": nombre,
            "partido": partido,
            "ocean_profile": perfil,
            "redes_sociales": redes,
            "desercion": desercion
        }
    except Exception as e:
        return {"error": str(e)}


@app.get('/rutas/brigada')
async def ruta_brigada(curps: str = Query(..., description='CURPs separadas por coma')):
    try:
        import clickhouse_connect
        client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''))
        lista_curps = [c.strip() for c in curps.split(',') if c.strip()]
        
        if len(lista_curps) < 2:
            return {'error': 'Se necesitan al menos 2 CURPs para trazar una ruta.'}
            
        query = f"SELECT curp, latitud, longitud FROM qsoy.votantes_csv WHERE curp IN {tuple(lista_curps)}"
        res = client.query(query).result_rows
        
        curps_coords = {}
        for r in res:
            curp, lat, lon = r
            if lat and lon and 15 < lat < 33 and -118 < lon < -86:
                curps_coords[curp] = (lat, lon)
                
        if len(curps_coords) < 2:
            return {'error': 'No se encontraron suficientes coordenadas válidas para las CURPs proporcionadas.'}
            
        resultado = calcular_ruta_optima(curps_coords)
        return resultado
        
    except Exception as e:
        return {'error': str(e)}

# ==========================================================
# CONFIGURACIÓN PARA SERVIR EL FRONTEND DESDE EL BACKEND
# ==========================================================
from fastapi.responses import HTMLResponse
import os

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'index.html')
    with open(frontend_path, 'r', encoding='utf-8') as f:
        return f.read()

# Servir archivos estáticos de la carpeta frontend (CSS, JS, GeoJSON)
from fastapi.staticfiles import StaticFiles
frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend_static")






import httpx

@app.get("/rutas/optimizar")
async def optimizar_ruta(lat_origen: float, lon_origen: float, lat_destino: float, lon_destino: float, modo: str = "auto"):
    """
    Trazar ruta optimizada. 
    Si es auto o moto, usa el puerto 5000 (perfil de auto).
    Si es caminando o transporte, usa el puerto 5001 (perfil peatonal).
    """
    if modo in ["caminando", "transporte"]:
        port = 5010 # Servidor peatonal
    else:
        port = 5000 # Servidor de autos
        
    profile = "foot" if modo in ["caminando", "transporte"] else "driving"
    osrm_url = f"http://127.0.0.1:{port}/route/v1/{profile}/{lon_origen},{lat_origen};{lon_destino},{lat_destino}?overview=full&geometries=geojson"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(osrm_url)
            data = response.json()
            
            if data.get("code") == "Ok":
                ruta = data["routes"][0]
                distancia_km = ruta["distance"] / 1000
                tiempo_base_min = ruta["duration"] / 60
                
                if modo == "moto":
                    tiempo_ajustado = tiempo_base_min * 0.75
                elif modo == "transporte":
                    tiempo_ajustado = tiempo_base_min * 1.4
                else:
                    tiempo_ajustado = tiempo_base_min
                    
                return {
                    "distancia_km": round(distancia_km, 2),
                    "duracion_minutos": round(tiempo_ajustado, 2),
                    "coordenadas": ruta["geometry"]["coordinates"],
                    "modo_usado": modo
                }
            else:
                return {"error": "No se pudo trazar la ruta", "detalle": data}
    except Exception as e:
        return {"error": "Motor OSRM no disponible", "detalle": str(e)}


# ============================================================
# ENDPOINTS DE TRANSPORTE PÚBLICO
# ============================================================
from fastapi.responses import FileResponse as FastAPIFileResponse

@app.get("/transporte/rutas")
async def get_rutas_transporte(ciudad: str = "", limit: int = 100):
    """Lista rutas de transporte desde ClickHouse"""
    try:
        client = get_ch_client()
        where = "1=1"
        params = {}
        if ciudad:
            where += " AND ciudad = %(ciudad)s"
            params["ciudad"] = ciudad
        sql = f"SELECT id, ciudad, nombre_ruta, origen, destino, distancia, num_paradas, operador, frecuencia, mapa_url FROM qsoy.rutas WHERE {where} ORDER BY ciudad, id LIMIT %(limit)s"
        params["limit"] = limit
        res = client.query(sql, parameters=params)
        cols = ["id","ciudad","nombre_ruta","origen","destino","distancia","num_paradas","operador","frecuencia","mapa_url"]
        return {"rutas": [dict(zip(cols, r)) for r in res.result_rows]}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/transporte/mapas/{filename}")
async def get_mapa_png(filename: str):
    """Sirve un mapa PNG de ruta de transporte"""
    import os
    filepath = os.path.join(os.path.dirname(__file__), '..', '5_datos_brutos', 'transporte_scraped', 'mapas_rutas', filename)
    if os.path.exists(filepath):
        return FastAPIFileResponse(filepath, media_type="image/png")
    raise HTTPException(404, f"Mapa {filename} no encontrado")

@app.get("/transporte/operadores")
async def get_operadores_transporte():
    """Lista operadores de transporte nacional"""
    import json as _json
    import os
    config_path = os.path.join(os.path.dirname(__file__), '..', '5_datos_brutos', 'transporte_scraped', 'operadores_transporte_nacional.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            return _json.load(f)
    return {"error": "No hay datos de operadores"}


# ============================================================
# ENDPOINTS DE API INEGI (RUTEO NACIONAL CON COSTOS)
# ============================================================
INEGI_KEY = "kqvCNH1V-keUF-rSVa-O1tf-gdqFN6DynMNN"
INEGI_BASE = "https://gaia.inegi.org.mx/sakbe_v3.1"

@app.post("/inegi/buscar")
async def inegi_buscar(destino: str = "", num: int = 10):
    """Busca destinos en la Red Nacional de Caminos del INEGI"""
    try:
        import requests as req
        r = req.post(f"{INEGI_BASE}/buscadestino",
            data={"buscar": destino, "type": "json", "num": num, "key": INEGI_KEY},
            headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=15)
        data = r.json()
        if data.get("response", {}).get("success"):
            return {"destinos": data.get("data", [])}
        return {"error": data.get("response", {}).get("message", "Error desconocido")}
    except Exception as e:
        return {"error": str(e)}

@app.post("/inegi/ruta")
async def inegi_ruta(origen: str, destino: str, vehiculo: int = 1, tipo_ruta: str = "optima"):
    """
    Calcula ruta entre dos ciudades con costo de peajes y combustible.
    vehiculo: 0=moto, 1=auto, 2=autobus_2ejes, 3=autobus_3ejes, 5=camion_2ejes
    tipo_ruta: optima, cuota, libre
    """
    try:
        import requests as req
        UA = {"User-Agent": "Mozilla/5.0"}
        
        # 1. Buscar ID de origen
        r = req.post(f"{INEGI_BASE}/buscadestino",
            data={"buscar": origen, "type": "json", "num": 1, "key": INEGI_KEY},
            headers=UA, verify=False, timeout=15)
        orig_data = r.json()
        if not orig_data.get("data"):
            return {"error": f"Origen '{origen}' no encontrado"}
        id_orig = orig_data["data"][0]["id_dest"]
        
        # 2. Buscar ID de destino
        r = req.post(f"{INEGI_BASE}/buscadestino",
            data={"buscar": destino, "type": "json", "num": 1, "key": INEGI_KEY},
            headers=UA, verify=False, timeout=15)
        dest_data = r.json()
        if not dest_data.get("data"):
            return {"error": f"Destino '{destino}' no encontrado"}
        id_dest = dest_data["data"][0]["id_dest"]
        
        # 3. Calcular ruta
        r = req.post(f"{INEGI_BASE}/{tipo_ruta}",
            data={"dest_i": id_orig, "dest_f": id_dest, "v": vehiculo, "type": "json", "key": INEGI_KEY},
            headers=UA, verify=False, timeout=30)
        ruta_data = r.json()
        
        if ruta_data.get("response", {}).get("success"):
            d = ruta_data["data"]
            
            # 4. Obtener precios de combustible
            r = req.post(f"{INEGI_BASE}/combustible",
                data={"type": "json", "key": INEGI_KEY}, headers=UA, verify=False, timeout=15)
            comb_data = r.json()
            combustible = {c.get("tipo",""): c.get("costo",0) for c in comb_data.get("data", [])}
            
            # 5. Calcular costo total
            costo_peaje = float(d.get("costo_caseta", 0))
            distancia_km = float(d.get("long_km", 0))
            tiempo_min = float(d.get("tiempo_min", 0))
            
            # Consumo: autobús ~2.5 km/L diesel, auto ~12 km/L
            consumo_km_l = {0: 35, 1: 12, 2: 2.5, 3: 2.0, 4: 1.5, 5: 4, 6: 3, 7: 2.5, 8: 2}
            consumo = consumo_km_l.get(vehiculo, 12)
            litros = distancia_km / consumo
            costo_combustible = litros * combustible.get("Diésel", combustible.get("Regular", 24))
            
            return {
                "origen": orig_data["data"][0]["nombre"],
                "destino": dest_data["data"][0]["nombre"],
                "distancia_km": distancia_km,
                "tiempo_min": tiempo_min,
                "tiempo_horas": round(tiempo_min / 60, 1),
                "tiene_peaje": d.get("peaje") == "t",
                "costo_peajes": costo_peaje,
                "costo_combustible": round(costo_combustible, 2),
                "costo_total": round(costo_peaje + costo_combustible, 2),
                "vehiculo": {0:"Moto",1:"Auto",2:"Autobús 2 ejes",3:"Autobús 3 ejes",
                             5:"Camión 2 ejes",6:"Camión 3 ejes"}.get(vehiculo, "Otro"),
                "combustible_precio": combustible,
                "litros_combustible": round(litros, 1),
                "geojson": d.get("geojson", ""),
                "tipo_ruta": tipo_ruta
            }
        return {"error": ruta_data.get("response", {}).get("message", "Error")}
    except Exception as e:
        return {"error": str(e)}

@app.get("/inegi/combustible")
async def inegi_combustible():
    """Obtiene precios actuales de combustible"""
    try:
        import requests as req
        r = req.post(f"{INEGI_BASE}/combustible",
            data={"type": "json", "key": INEGI_KEY},
            headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=15)
        data = r.json()
        if data.get("response", {}).get("success"):
            return {"combustible": data.get("data", [])}
        return {"error": "No disponible"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/inegi/costo_movilizacion")
async def inegi_costo_movilizacion(origen: str, destino: str, num_personas: int = 100):
    """
    Calcula el costo de mover N personas de una ciudad a otra.
    Compara: autobús rentado vs autos individuales vs vuelos.
    """
    try:
        # Calcular ruta para autobús (v=2)
        ruta = await inegi_ruta(origen, destino, vehiculo=2, tipo_ruta="optima")
        if "error" in ruta:
            return ruta
        
        dist = ruta["distancia_km"]
        tiempo = ruta["tiempo_horas"]
        peaje = ruta["costo_peajes"]
        combustible = ruta["costo_combustible"]
        
        # Opción 1: Autobús rentado (50 pax por bus)
        num_buses = (num_personas + 49) // 50
        costo_bus_peaje = peaje * num_buses
        costo_bus_comb = combustible * num_buses
        costo_bus_renta = num_buses * 8000 * max(1, tiempo/8)  # $8,000/día por bus
        costo_bus_total = costo_bus_peaje + costo_bus_comb + costo_bus_renta
        
        # Opción 2: Autos (5 pax por auto, v=1)
        num_autos = (num_personas + 4) // 5
        # Recalcular combustible para auto
        litros_auto = dist / 12  # 12 km/L
        costo_auto_comb = litros_auto * 24  # ~$24/L regular
        costo_auto_peaje = peaje * 0.5  # Autos pagan menos peaje aprox
        costo_auto_gas = num_autos * (costo_auto_comb + costo_auto_peaje)
        
        # Opción 3: Vuelo (estimado)
        costo_vuelo = num_personas * 2500  # ~$2,500 por persona promedio
        
        return {
            "origen": ruta["origen"],
            "destino": ruta["destino"],
            "distancia_km": dist,
            "tiempo_horas": tiempo,
            "num_personas": num_personas,
            "opciones": {
                "autobus_rentado": {
                    "num_buses": num_buses,
                    "peajes": round(costo_bus_peaje, 2),
                    "combustible": round(costo_bus_comb, 2),
                    "renta": round(costo_bus_renta, 2),
                    "total": round(costo_bus_total, 2),
                    "costo_por_persona": round(costo_bus_total / num_personas, 2)
                },
                "autos_individuales": {
                    "num_autos": num_autos,
                    "combustible": round(costo_auto_gas, 2),
                    "total": round(costo_auto_gas, 2),
                    "costo_por_persona": round(costo_auto_gas / num_personas, 2)
                },
                "vuelo_estimado": {
                    "total": costo_vuelo,
                    "costo_por_persona": 2500
                }
            },
            "recomendacion": "autobus" if costo_bus_total < costo_auto_gas and costo_bus_total < costo_vuelo else ("auto" if costo_auto_gas < costo_vuelo else "vuelo")
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# ENDPOINTS MAPA DE CALOR + PERFILES
# ============================================================
@app.get("/afiliados/heatmap")
async def afiliados_heatmap(estado: str = "", limit: int = 1000):
    try:
        client = get_ch_client()
        where = "1=1"
        params = {"limit": limit}
        if estado:
            where += " AND entidad = %(estado)s"
            params["estado"] = estado
        sql = f"SELECT entidad, seccion, total_afiliados, con_gps, lat_centro, lon_centro, partido FROM qsoy.densidad_afiliados WHERE {where} ORDER BY total_afiliados DESC LIMIT %(limit)s"
        res = client.query(sql, parameters=params)
        cols = ["entidad","seccion","total_afiliados","con_gps","lat","lon","partido"]
        return {"total_secciones": len(res.result_rows), "puntos": [dict(zip(cols, r)) for r in res.result_rows]}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/candidatos/perfil/{nombre}")
async def candidato_perfil(nombre: str):
    try:
        client = get_ch_client()
        cols_res = client.query("DESCRIBE qsoy.ine_candidatos_2024")
        cols = [r[0] for r in cols_res.result_rows]
        res = client.query(f"SELECT * FROM qsoy.ine_candidatos_2024 WHERE nombre_candidato ILIKE '%{nombre}%' LIMIT 5")
        return {"candidatos": [dict(zip(cols, row)) for row in res.result_rows]}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/resultados/casillas")
async def resultados_casillas(estado: int = 0, limit: int = 5000):
    try:
        client = get_ch_client()
        where = "1=1"
        params = {"limit": limit}
        if estado and estado > 0:
            where += " AND estado = %(estado)s"
            params["estado"] = estado
        sql = "SELECT seccion, lat_casilla, lon_casilla, partido_ganador, candidato_ganador, votos_ganador, total_votos, pct FROM qsoy.ganadores_casillas WHERE " + where + " AND lat_casilla > 0 LIMIT %(limit)s"
        res = client.query(sql, parameters=params)
        cols = ["seccion","lat","lon","partido","candidato","votos","total","pct"]
        data = [dict(zip(cols, r)) for r in res.result_rows]
        from collections import Counter
        partidos = Counter(d["partido"] for d in data)
        return {"total_casillas": len(data), "casillas": data, "resumen_partidos": dict(partidos.most_common(10))}
    except Exception as e:
        raise HTTPException(500, str(e))

# ============================================================
# NUEVOS ENDPOINTS: INTELIGENCIA INEGI + INFERENCIA DE CURP
# ============================================================

@app.get("/api/perfil_demografico")
def perfil_demografico(estado: str, municipio: str = "000"):
    """
    Devuelve el perfil sociodemográfico de un estado o municipio basado en el Censo INEGI 2020.
    Incluye religión, escolaridad, empleo y servicios.
    """
    est = safe(estado)
    mun = safe(municipio)
    
    # Buscar el total del municipio (LOC = 0000 usualmente es el total municipal o estatal)
    sql = f"""
    SELECT 
        POBTOT, POBFEM, POBMAS, 
        PCATOLICA, PRO_CRIEVA, PSIN_RELIG,
        GRAPROES, PEA, POCUPADA, PDESOCUP,
        VPH_INTER, VPH_CEL
    FROM qsoy.inegi_iter_2020 
    WHERE ENTIDAD = '{est}' AND MUN = '{mun}'
    AND LOC = '0000'
    LIMIT 1
    """
    res = q(sql)
    if not res:
        raise HTTPException(status_code=404, detail="No se encontraron datos para esta ubicación")
        
    r = res[0]
    return {
        "poblacion_total": r[0],
        "poblacion_mujeres": r[1],
        "poblacion_hombres": r[2],
        "religion": {
            "catolica": r[3],
            "evangelica": r[4],
            "sin_religion": r[5]
        },
        "escolaridad_promedio": r[6],
        "economia": {
            "activa": r[7],
            "ocupada": r[8],
            "desocupada": r[9]
        },
        "tecnologia": {
            "viviendas_con_internet": r[10],
            "viviendas_con_celular": r[11]
        }
    }

@app.get("/api/paridad/verificar")
def verificar_paridad(estado: str, municipio: str):
    """
    Verifica si una zona cumple con criterios de paridad transversal
    (alta presencia de afrodescendientes o personas con discapacidad).
    """
    est = safe(estado)
    mun = safe(municipio)
    
    sql = f"""
    SELECT 
        NOM_MUN, POBTOT, POB_AFRO, PCON_DISC, PHOG_IND
    FROM qsoy.inegi_iter_2020 
    WHERE ENTIDAD = '{est}' AND MUN = '{mun}'
    AND LOC = '0000'
    LIMIT 1
    """
    res = q(sql)
    if not res:
        raise HTTPException(status_code=404, detail="Municipio no encontrado en INEGI")
        
    r = res[0]
    municipio_nombre, pob_tot, pob_afro, pob_disc, pob_ind = r
    
    # Calcular porcentajes
    pct_afro = (int(pob_afro) / int(pob_tot) * 100) if int(pob_tot) > 0 else 0
    pct_disc = (int(pob_disc) / int(pob_tot) * 100) if int(pob_tot) > 0 else 0
    pct_ind = (int(pob_ind) / int(pob_tot) * 100) if int(pob_tot) > 0 else 0
    
    alertas = []
    if pct_afro > 10: alertas.append("Zona con población afrodescendiente significativa")
    if pct_disc > 15: alertas.append("Zona con alta población con discapacidad")
    if pct_ind > 40: alertas.append("Zona indígena (cuota obligatoria)")
    
    return {
        "municipio": municipio_nombre,
        "poblacion_total": pob_tot,
        "porcentaje_afrodescendiente": round(pct_afro, 2),
        "porcentaje_discapacidad": round(pct_disc, 2),
        "porcentaje_indigena": round(pct_ind, 2),
        "cumple_criterio_paridad": len(alertas) > 0,
        "alertas": alertas
    }

@app.get("/api/curp/inferir")
def inferir_curp(nombre: str, paterno: str, materno: str, sexo: Optional[str] = None, edad: Optional[str] = None, estado: Optional[str] = None):
    """
    Motor de inferencia de CURP. Busca en el padrón de 95 millones por nombre exacto.
    Si hay múltiples resultados, permite filtrar por sexo, edad o estado para encontrar el match único.
    """
    n = safe(nombre.upper())
    p = safe(paterno.upper())
    m = safe(materno.upper())
    
    sql = f"""
    SELECT curp, nombre, paterno, materno, edad, sexo, e, m, colonia, cp, latitud, longitud
    FROM qsoy.votantes_csv 
    WHERE UPPER(nombre) = '{n}' 
    AND UPPER(paterno) = '{p}'
    AND UPPER(materno) = '{m}'
    """
    
    if sexo:
        s = safe(sexo.upper())
        sql += f" AND UPPER(sexo) = '{s}'"
    
    if edad:
        e_val = safe(edad)
        sql += f" AND edad = '{e_val}'"
        
    if estado:
        est = safe(estado)
        sql += f" AND e = '{est}'"
        
    sql += " LIMIT 20"
    
    res = q(sql)
    
    if not res:
        raise HTTPException(status_code=404, detail="No se encontraron coincidencias en el padrón")
        
    resultados = []
    for r in res:
        resultados.append({
            "curp": r[0],
            "nombre_completo": f"{r[1]} {r[2]} {r[3]}",
            "edad": r[4],
            "sexo": r[5],
            "estado_id": r[6],
            "municipio_id": r[7],
            "colonia": r[8],
            "cp": r[9],
            "latitud": r[10],
            "longitud": r[11]
        })
        
    match_unico = len(resultados) == 1
    
    return {
        "total_encontrados": len(resultados),
        "match_unico": match_unico,
        "resultados": resultados,
        "mensaje": "CURP inferida con éxito" if match_unico else "Múltiples resultados. Proporcione más filtros (sexo, edad, estado) para aislar el registro."
    }
