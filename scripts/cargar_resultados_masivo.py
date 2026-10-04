import pandas as pd
import glob
import os
import clickhouse_connect
import warnings
import re
warnings.filterwarnings('ignore')

# Conexión a ClickHouse
client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''))
print("✅ Conectado a ClickHouse.")

# Palabras que indican el inicio de la tabla
PALABRAS_ENCABEZADO = ['DISTRITO', 'CASILLA', 'TIPO_CASILLA', 'ID_CASILLA', 'SECCION']
# Palabras que NO son partidos (son metadatos de la casilla)
METADATOS = ['DISTRITO', 'CABECERA', 'MUNICIPIO', 'SECCION', 'CASILLA', 'TIPO', 'ID', 'LISTA', 'NOMBRE', 'ESTADO', 'LOCAL', 'NO', 'VOTACION', 'TOTAL', 'NULOS']

def extraer_anio_tipo(archivo):
    """Extrae el año y tipo de elección del nombre del archivo"""
    anio = 0
    tipo = "DESCONOCIDO"
    
    if "2024" in archivo: anio = 2024
    elif "2021" in archivo: anio = 2021
    elif "2018" in archivo: anio = 2018
    
    if "GUBERNATURA" in archivo.upper(): tipo = "GUBERNATURA"
    elif "AYUNTAMIENTO" in archivo.upper() or "MUNICIPAL" in archivo.upper(): tipo = "AYUNTAMIENTO"
    elif "DIPUTACION" in archivo.upper() or "DIPUTADO" in archivo.upper() or "CDE" in archivo.upper(): tipo = "DIPUTADO MR"
    
    return anio, tipo

def encontrar_fila_encabezado(archivo):
    """Lee las primeras 20 filas para encontrar dónde empiezan los encabezados reales."""
    df_temp = pd.read_excel(archivo, sheet_name=0, header=None, nrows=20)
    for i, row in df_temp.iterrows():
        for val in row:
            if isinstance(val, str) and any(pal in val.upper() for pal in ['CASILLA', 'DISTRITO', 'TIPO_CASILLA']):
                return i
    return 0

def procesar_archivo(archivo, estado_id):
    try:
        skip = encontrar_fila_encabezado(archivo)
        df = pd.read_excel(archivo, sheet_name=0, header=skip)
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Identificar columnas de partidos (las que no son metadatos)
        col_distrito = [c for c in df.columns if 'DISTRITO' in c][0] if any('DISTRITO' in c for c in df.columns) else None
        col_casilla = [c for c in df.columns if 'CASILLA' in c][0] if any('CASILLA' in c for c in df.columns) else None
        
        if not col_casilla and not col_distrito:
            return None
            
        cols_partidos = [c for c in df.columns if c not in METADATOS and not c.startswith('UNNAMED')]
        
        if not cols_partidos:
            return None
            
        # Quedarnos solo con filas que tengan datos en la casilla o distrito
        if col_casilla:
            df = df[df[col_casilla].notna()]
        elif col_distrito:
            df = df[df[col_distrito].notna()]
            
        # Transformar de columnas a filas (Melt)
        id_vars = [c for c in [col_distrito, col_casilla] if c]
        df_melted = pd.melt(df, id_vars=id_vars, value_vars=cols_partidos, var_name='partido', value_name='votos')
        
        # Limpieza final
        df_melted['votos'] = pd.to_numeric(df_melted['votos'], errors='coerce').fillna(0).astype(int)
        df_melted = df_melted[df_melted['votos'] > 0]
        
        anio, tipo = extraer_anio_tipo(archivo)
        df_melted['anio'] = anio
        df_melted['tipo_eleccion'] = tipo
        df_melted['estado'] = estado_id
        df_melted['distrito'] = pd.to_numeric(df_melted[col_distrito], errors='coerce').fillna(0).astype(int) if col_distrito else 0
        df_melted['municipio'] = 0
        df_melted['candidato'] = ''
        df_melted['fuente'] = 'CSV/XLS Local'
        
        # Ordenar columnas para ClickHouse
        columnas_finales = ['anio', 'tipo_eleccion', 'estado', 'distrito', 'municipio', 'partido', 'candidato', 'votos', 'fuente']
        return df_melted[columnas_finales]
        
    except Exception as e:
        print(f"  ⚠️ Error en {os.path.basename(archivo)}: {str(e)[:80]}")
        return None

datos_totales = []

# 1. Procesar Puebla (Estado 21)
print("\n📊 PROCESANDO PUEBLA (Estado 21)...")
for f in glob.glob('datos_puebla/*.xlsx'):
    print(f"  📄 Leyendo: {os.path.basename(f)}")
    df_res = procesar_archivo(f, 21)
    if df_res is not None and len(df_res) > 0:
        datos_totales.append(df_res)
        print(f"     ✅ {len(df_res)} registros válidos encontrados.")

# 2. Procesar Tamaulipas (Estado 28)
print("\n📊 PROCESANDO TAMAULIPAS (Estado 28)...")
for f in glob.glob('datos_tamaulipas/*.xlsx'):
    print(f"  📄 Leyendo: {os.path.basename(f)}")
    df_res = procesar_archivo(f, 28)
    if df_res is not None and len(df_res) > 0:
        datos_totales.append(df_res)
        print(f"     ✅ {len(df_res)} registros válidos encontrados.")

# 3. Insertar en ClickHouse
if datos_totales:
    print(f"\n⏳ Concatenando {len(datos_totales)} DataFrames...")
    df_final = pd.concat(datos_totales, ignore_index=True)
    print(f"📊 Total de registros a insertar: {len(df_final)}")
    
    print("⏳ Insertando en ClickHouse (tabla resultados_electorales)...")
    client.insert_df('qsoy.resultados_electorales', df_final)
    print("✅ ¡INSERCIÓN COMPLETADA CON ÉXITO!")
else:
    print("❌ No se encontraron datos válidos para insertar.")
