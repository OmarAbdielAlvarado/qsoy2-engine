import pandas as pd
import clickhouse_connect
import os
import glob
import time

# Configuración
PADRON_DIR = os.path.expanduser('~/proyectos/QSoy2/5_datos_brutos/padrones_ine/')
CLICKHOUSE_HOST = 'localhost'
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = os.environ.get('CLICKHOUSE_PASSWORD','')
DB_NAME = 'qsoy'
TABLE_NAME = 'afiliados_ine'

def main():
    print("🔌 Conectando a ClickHouse...")
    client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, username=CLICKHOUSE_USER, password=CLICKHOUSE_PASSWORD, database=DB_NAME)

    # Crear tabla unificada para todos los partidos
    print(f"🗄️  Creando tabla {TABLE_NAME} si no existe...")
    client.command(f'''
    CREATE TABLE IF NOT EXISTS {DB_NAME}.{TABLE_NAME} (
        partido String,
        clave_elector String,
        nombre String,
        apellido_paterno String,
        apellido_materno String,
        fecha_afiliacion String,
        seccion String
    ) ENGINE = MergeTree()
    ORDER BY (partido, seccion)
    ''')

    # Limpiar la tabla por si ya tenía datos
    client.command(f'TRUNCATE TABLE {DB_NAME}.{TABLE_NAME}')

    files = glob.glob(os.path.join(PADRON_DIR, 'PADRON_*.xlsx'))

    for file in files:
        # Extraer nombre del partido del nombre del archivo
        partido_name = os.path.basename(file).replace('PADRON_', '').replace('_2023', '').replace('-1', '').replace('.xlsx', '')
        print(f"\n📁 Procesando partido: {partido_name}")
        
        # 1. Detectar filas de título (skiprows dinámico)
        df_head = pd.read_excel(file, nrows=15, header=None)
        skiprows = 0
        for i, row in df_head.iterrows():
            # Si encuentra una celda que diga CLAVE o NOMBRE, asume que es el header
            if any(isinstance(x, str) and ('CLAVE' in x.upper() or 'NOMBRE' in x.upper()) for x in row):
                skiprows = i
                break
                
        print(f"   -> Saltando {skiprows} filas de título...")
        
        # 2. Leer el Excel completo
        print("   -> Leyendo Excel...")
        df = pd.read_excel(file, skiprows=skiprows)
        
        # Limpiar nombres de columnas
        df.columns = [str(c).strip().upper().replace(' ', '_').replace('DE_', '') for c in df.columns]
        
        print(f"   -> Columnas detectadas: {list(df.columns)}")
        
        # 3. Mapear columnas (resiliente a cambios de nombre)
        col_map = {}
        for col in df.columns:
            if 'CLAVE' in col and 'ELECTOR' in col: col_map[col] = 'clave_elector'
            elif 'NOMBRE' in col and 'APELLIDO' not in col: col_map[col] = 'nombre'
            elif 'PATERNO' in col: col_map[col] = 'apellido_paterno'
            elif 'MATERNO' in col: col_map[col] = 'apellido_materno'
            elif 'AFILIACION' in col: col_map[col] = 'fecha_afiliacion'
            elif 'SECCION' in col or 'SECCIÓN' in col: col_map[col] = 'seccion'
            
        df = df.rename(columns=col_map)
        
        # Asegurar que tenemos las columnas necesarias
        required = ['clave_elector', 'nombre', 'apellido_paterno', 'apellido_materno', 'fecha_afiliacion', 'seccion']
        for req in required:
            if req not in df.columns:
                df[req] = ''
                
        # Filtrar solo las columnas que necesitamos y agregar el partido
        df_clean = df[required].copy()
        df_clean['partido'] = partido_name
        
        # Limpiar nulos (ClickHouse falla si hay NaN en Strings)
        df_clean = df_clean.fillna('')
        
        # Convertir todo a string
        for col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(str)
            
        print(f"   -> {len(df_clean)} registros a insertar...")
        
        # 4. Insertar en ClickHouse en lotes
        start_time = time.time()
        client.insert_df(f'{DB_NAME}.{TABLE_NAME}', df_clean)
        
        elapsed = time.time() - start_time
        print(f"   ✅ Insertado en {elapsed:.2f}s")

    print("\n🎉 ¡Proceso completado! Verificando totales:")
    result = client.query(f'SELECT partido, count() as total FROM {DB_NAME}.{TABLE_NAME} GROUP BY partido ORDER BY total DESC')
    for row in result.result_rows:
        print(f"   {row[0]}: {row[1]:,} afiliados")

if __name__ == "__main__":
    main()
