import pandas as pd
import os
import clickhouse_connect

BASE_DIR = os.path.expanduser('~/proyectos/QSoy2/5_datos_brutos/resultados_electorales/judicial_2025/nacional_zip/csv_extraidos/')

# Mapeo: archivo de votos -> (archivo de candidaturas, nombre del cargo)
archivos = {
    "MIN_2025.csv": ("MIN_CANDIDATURAS_2025.csv", "MINISTRO/A SCJN"),
    "MAG_SS_2025.csv": ("MAG_SS_CANDIDATURAS_2025.csv", "MAGISTRADO/A TEPJF SS"),
    "MAG_SR_2025.csv": ("MAG_SR_CANDIDATURAS_2025.csv", "MAGISTRADO/A TEPJF SR"),
    "MAG_TDJ_2025.csv": ("MAG_TDJ_CANDIDATURAS_2025.csv", "MAGISTRADO/A TDJ"),
    "MAG_TC_2025.csv": ("MAG_TC_CANDIDATURAS_2025.csv", "MAGISTRADO/A TC"),
    "JUZ_2025.csv": ("JUZ_CANDIDATURAS_2025.csv", "JUEZ/A DISTRITO"),
}

print("📊 Conectando a ClickHouse...")
client = clickhouse_connect.get_client(host='localhost', username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''), database='qsoy')

# Crear tabla limpia (formato largo)
client.command("""
CREATE TABLE IF NOT EXISTS resultados_judicial_nacional (
    cargo String,
    entidad String,
    distrito_federal String,
    seccion UInt32,
    clave_casilla String,
    candidato String,
    poder_postulante String,
    votos UInt32
) ENGINE = MergeTree() ORDER BY (cargo, entidad, seccion)
""")
client.command("TRUNCATE TABLE resultados_judicial_nacional")
print("🧹 Tabla limpia. Iniciando carga masiva...")

for votos_file, (cand_file, cargo) in archivos.items():
    print(f"\n-> Procesando {votos_file}...")
    votos_path = os.path.join(BASE_DIR, votos_file)
    cand_path = os.path.join(BASE_DIR, cand_file)
    
    # 1. Leer Votos (saltando las 6 líneas de basura del INE)
    df = pd.read_csv(votos_path, skiprows=6, low_memory=False, on_bad_lines='skip', dtype={'SECCION': 'Int32'})
    
    # Identificar columnas clave y columnas de candidatos (CAND01, CAND02...)
    id_cols = ['CLAVE_CASILLA', 'ENTIDAD', 'DISTRITO_FEDERAL', 'SECCION']
    id_cols = [c for c in id_cols if c in df.columns] # Asegurar que existan
    cand_cols = [c for c in df.columns if c.startswith('CAND')]
    
    # Unpivot (de ancho a largo)
    df_melt = df.melt(id_vars=id_cols, value_vars=cand_cols, var_name='CAND_ID', value_name='VOTOS_STR')
    
    # Limpiar votos (eliminar "-" y convertir a número)
    df_melt['VOTOS_STR'] = df_melt['VOTOS_STR'].astype(str).str.replace('-', '0', regex=False)
    df_melt['votos'] = pd.to_numeric(df_melt['VOTOS_STR'], errors='coerce').fillna(0).astype(int)
    df_melt = df_melt[df_melt['votos'] > 0] # Ignitar filas con 0 votos para ahorrar espacio
    
    # 2. Leer Candidaturas (saltando las 2 líneas de basura)
    df_cand = pd.read_csv(cand_path, skiprows=2, header=None, on_bad_lines='skip')
    
    # El INE pone IDs antes de CAND_ID. Buscamos la columna que contiene 'CAND01'
    cand_col_idx = None
    for i, col in enumerate(df_cand.columns):
        if df_cand[col].astype(str).str.startswith('CAND').any():
            cand_col_idx = i
            break
            
    if cand_col_idx is not None:
        # ID está en cand_col_idx, Nombre en +1, Partido en +3 (o +2 si no hay especialidad)
        party_idx = cand_col_idx + 3 if (cand_col_idx + 3) < len(df_cand.columns) else cand_col_idx + 2
        df_cand_clean = df_cand.iloc[:, [cand_col_idx, cand_col_idx+1, party_idx]].copy()
        df_cand_clean.columns = ['CAND_ID', 'candidato', 'poder_postulante']
    else:
        df_cand_clean = pd.DataFrame(columns=['CAND_ID', 'candidato', 'poder_postulante'])
        
    # 3. Unir votos con nombres
    df_final = df_melt.merge(df_cand_clean, on='CAND_ID', how='left')
    
    # Formatear para ClickHouse
    df_final['cargo'] = cargo
    df_final = df_final.rename(columns={
        'CLAVE_CASILLA': 'clave_casilla', 'ENTIDAD': 'entidad', 
        'DISTRITO_FEDERAL': 'distrito_federal', 'SECCION': 'seccion'
    })
    
    # Rellenar nulos
    df_final['candidato'] = df_final['candidato'].fillna('N/A').str.upper()
    df_final['poder_postulante'] = df_final['poder_postulante'].fillna('N/A')
    df_final['distrito_federal'] = df_final['distrito_federal'].fillna('N/A')
    df_final['clave_casilla'] = df_final['clave_casilla'].fillna('N/A')
    df_final['seccion'] = df_final['seccion'].fillna(0).astype(int)
    
    # 4. Insertar a ClickHouse
    cols_to_insert = ['cargo', 'entidad', 'distrito_federal', 'seccion', 'clave_casilla', 'candidato', 'poder_postulante', 'votos']
    client.insert_df('resultados_judicial_nacional', df_final[cols_to_insert])
    print(f"   ✅ {len(df_final)} registros insertados.")

print("\n" + "="*50)
print("🎯 REPORTE NACIONAL: PERDEDORES FUERTES Y SERGIO FLORES")
print("="*50)

print("\n🔥 Top 10 Perdedores Fuertes Nacionales (>15,000 votos):")
res = client.query("""
    SELECT cargo, candidato, sum(votos) as total_votos 
    FROM resultados_judicial_nacional 
    GROUP BY cargo, candidato 
    HAVING total_votos > 15000 
    ORDER BY total_votos DESC 
    LIMIT 10
""")
for row in res.result_rows:
    print(f"  -> {row[1]} ({row[0]}): {row[2]:,} votos")

print("\n🧔 Búsqueda de Sergio Flores (nacional):")
res = client.query("""
    SELECT cargo, entidad, candidato, sum(votos) as total_votos 
    FROM resultados_judicial_nacional 
    WHERE candidato ILIKE '%SERGIO%' AND candidato ILIKE '%FLORES%'
    GROUP BY cargo, entidad, candidato
""")
if res.result_rows:
    for row in res.result_rows:
        print(f"  -> {row[2]} | {row[0]} en {row[1]}: {row[3]:,} votos")
else:
    print("  -> No se encontró a Sergio Flores en el padrón federal del INE.")
