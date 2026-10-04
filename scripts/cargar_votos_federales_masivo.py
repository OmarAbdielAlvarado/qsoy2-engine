import pandas as pd
import clickhouse_connect
import os
import re
import warnings
warnings.filterwarnings('ignore')

base_dir = '/home/omar/proyectos/QSoy2/datos_hidalgo/elecRetrns/datosBrutos/result-casillas-fed/'
client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''), database='qsoy')

print("🛰️ Escaneando todas las elecciones federales...")

total_insertado = 0

for root, _, files in os.walk(base_dir):
    for file in files:
        if file.endswith('.csv') and 'lonlat' not in file.lower() and 'candid' not in file.lower() and 'lisnom' not in file.lower() and 'nuladas' not in file.lower():
            filepath = os.path.join(root, file)
            
            # Extraer año y tipo del nombre (ej. "Presidente2018.csv" -> 2018, PRESIDENTE)
            match_anio = re.search(r'(\d{4})', file)
            anio = int(match_anio.group(1)) if match_anio else 0
            
            if 'PRES' in file.upper():
                tipo = 'PRESIDENTE'
            elif 'DIP' in file.upper():
                tipo = 'DIPUTADO'
            elif 'SEN' in file.upper():
                tipo = 'SENADOR'
            else:
                tipo = 'FEDERAL'
            
            print(f"\n📥 Procesando: {file} (Año: {anio}, Tipo: {tipo})")
            try:
                df = pd.read_csv(filepath, encoding='latin-1', on_bad_lines='skip')
                df.columns = df.columns.str.strip().str.upper()
                
                # Identificar columnas de metadata (suelen ser las primeras)
                meta_cols = [c for c in ['EDON', 'EDO', 'ESTADO', 'DISN', 'MUNN', 'MUN', 'SECCION', 'CASILLA', 'TIPO_CASILLA'] if c in df.columns]
                if not meta_cols:
                    continue # Si no tiene estas columnas, no es un archivo de resultados
                    
                # Las columnas de partidos son el resto, excluyendo totales y listas nominales
                excluir = ['NR', 'NUL', 'TOT', 'LISNOM', 'STATUS', 'TEPJF', 'NOTA', 'OBS', 'ID', 'ORD', 'IFE', 'INEGI']
                partidos_cols = [c for c in df.columns if c not in meta_cols and not any(ex in c for ex in excluir) and df[c].dtype in ['int64', 'float64']]
                
                if not partidos_cols:
                    continue

                df_largo = df.melt(id_vars=meta_cols, value_vars=partidos_cols, var_name='partido', value_name='votos')
                df_largo['votos'] = pd.to_numeric(df_largo['votos'], errors='coerce').fillna(0).astype(int)
                df_largo = df_largo[df_largo['votos'] > 0]
                
                df_final = pd.DataFrame({
                    'anio': anio,
                    'tipo_eleccion': tipo,
                    'estado': pd.to_numeric(df_largo.get('EDON', df_largo.get('EDO', 0)), errors='coerce').fillna(0).astype(int),
                    'distrito': pd.to_numeric(df_largo.get('DISN', 0), errors='coerce').fillna(0).astype(int),
                    'municipio': pd.to_numeric(df_largo.get('MUNN', df_largo.get('MUN', 0)), errors='coerce').fillna(0).astype(int),
                    'partido': df_largo['partido'].astype(str),
                    'candidato': '',
                    'votos': df_largo['votos'],
                    'fuente': f'CSV_FED_{anio}'
                })
                
                if not df_final.empty:
                    print(f"   🚀 Insertando {len(df_final)} registros...")
                    client.insert_df('resultados_electorales', df_final)
                    total_insertado += len(df_final)
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")

print(f"\n✅ ¡Carga masiva federal completada! Total insertado: {total_insertado} registros.")
