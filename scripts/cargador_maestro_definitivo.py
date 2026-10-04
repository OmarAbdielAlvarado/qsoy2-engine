import pandas as pd
import clickhouse_connect
import os
import re
import warnings
warnings.filterwarnings('ignore')

client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''), database='qsoy')

# Diccionario para mapear las abreviaturas de los archivos a ID de estado
state_map = {
    'ags': 1, 'bc': 2, 'bcs': 3, 'cam': 4, 'coa': 5, 'col': 6, 'cps': 7, 'cua': 8, 'df': 9, 'mex': 15, 
    'mor': 17, 'mich': 16, 'nap': 18, 'nl': 19, 'oax': 20, 'pue': 21, 'qro': 22, 'roo': 23, 
    'slp': 24, 'sin': 25, 'son': 26, 'tab': 27, 'tam': 28, 'tla': 29, 'ver': 30, 'yuc': 31, 'zac': 32,
    'gua': 11, 'hgo': 13, 'jal': 14, 'mic': 16, 'nay': 18, 'san': 24
}

def get_col(df, col_name):
    """Obtiene una columna del DataFrame de forma segura, si no existe devuelve una vacía"""
    return df[col_name] if col_name in df.columns else pd.Series(0, index=df.index)

carpetas = [
    '/home/omar/proyectos/QSoy2/datos_hidalgo/elecRetrns/datosBrutos/result-casillas-fed/',
    '/home/omar/proyectos/QSoy2/datos_hidalgo/elecRetrns/datosBrutos/result-casillas-subnat/'
]

total_insertado = 0

print("🚀 Iniciando Cargador Maestro Definitivo (Federales y Locales)...\n")

for carpeta in carpetas:
    for root, _, files in os.walk(carpeta):
        for file in files:
            if file.endswith(('.csv', '.xlsx', '.xls')) and 'lonlat' not in file.lower() and 'candid' not in file.lower() and 'lisnom' not in file.lower():
                filepath = os.path.join(root, file)
                
                # Extraer año
                match_anio = re.search(r'(\d{4})', file)
                anio = int(match_anio.group(1)) if match_anio else 0
                
                # Extraer estado (si es local, los primeros 3 letras)
                estado_id = 0
                tipo_eleccion = 'FEDERAL'
                if 'fed' not in file.lower():
                    for abrev, eid in state_map.items():
                        if file.lower().startswith(abrev):
                            estado_id = eid
                            if 'ay' in file.lower() or 'ayca' in file.lower(): tipo_eleccion = 'MUNICIPAL'
                            elif 'dl' in file.lower() or 'dlca' in file.lower(): tipo_eleccion = 'DIPUTADO_LOCAL'
                            elif 'go' in file.lower() or 'goca' in file.lower(): tipo_eleccion = 'GOBERNADOR'
                            break
                else:
                    if 'PRES' in file.upper(): tipo_eleccion = 'PRESIDENTE'
                    elif 'DIP' in file.upper(): tipo_eleccion = 'DIPUTADO'
                    elif 'SEN' in file.upper(): tipo_eleccion = 'SENADOR'

                try:
                    # Leer archivo
                    if file.endswith('.csv'):
                        df = pd.read_csv(filepath, encoding='latin-1', on_bad_lines='skip', sep=None, engine='python')
                    else:
                        df = pd.read_excel(filepath)
                        
                    df.columns = df.columns.str.strip().str.upper()
                    
                    # Identificar columnas de metadata de forma segura
                    meta_cols = [c for c in ['EDON', 'EDO', 'ESTADO', 'DISN', 'MUNN', 'MUN', 'SECCION', 'CASILLA'] if c in df.columns]
                    if not meta_cols: continue
                    
                    # Excluir columnas que no son partidos
                    excluir = ['NR', 'NUL', 'TOT', 'LISNOM', 'STATUS', 'TEPJF', 'NOTA', 'OBS', 'ID', 'ORD', 'IFE', 'INEGI', 'LATITUDE', 'LONGITUDE']
                    partidos_cols = [c for c in df.columns if c not in meta_cols and not any(ex in c for ex in excluir) and df[c].dtype in ['int64', 'float64']]
                    
                    if not partidos_cols: continue

                    df_largo = df.melt(id_vars=meta_cols, value_vars=partidos_cols, var_name='partido', value_name='votos')
                    df_largo['votos'] = pd.to_numeric(df_largo['votos'], errors='coerce').fillna(0).astype(int)
                    df_largo = df_largo[df_largo['votos'] > 0]
                    
                    # Construir DataFrame final usando get_col para evitar el error de 'int' object
                    df_final = pd.DataFrame({
                        'anio': anio,
                        'tipo_eleccion': tipo_eleccion,
                        'estado': pd.to_numeric(get_col(df_largo, 'EDON') if 'EDON' in df_largo.columns else (get_col(df_largo, 'EDO') if 'EDO' in df_largo.columns else get_col(df_largo, 'ESTADO')), errors='coerce').fillna(0).astype(int)
                    })
                    if df_final['estado'].eq(0).all() and estado_id != 0:
                        df_final['estado'] = estado_id
                        
                    df_final['distrito'] = pd.to_numeric(get_col(df_largo, 'DISN'), errors='coerce').fillna(0).astype(int)
                    df_final['municipio'] = pd.to_numeric(get_col(df_largo, 'MUNN') if 'MUNN' in df_largo.columns else get_col(df_largo, 'MUN'), errors='coerce').fillna(0).astype(int)
                    df_final['partido'] = df_largo['partido'].astype(str)
                    df_final['candidato'] = ''
                    df_final['votos'] = df_largo['votos']
                    df_final['fuente'] = f'MASTER_{file[:20]}'
                    
                    if not df_final.empty:
                        print(f"📥 {file[:30]} ({anio} - {tipo_eleccion}) -> {len(df_final)} registros")
                        client.insert_df('resultados_electorales', df_final)
                        total_insertado += len(df_final)
                        
                except Exception as e:
                    print(f"❌ Error en {file}: {e}")

print(f"\n✅ ¡Carga Maestra completada! Total insertado: {total_insertado} registros.")
