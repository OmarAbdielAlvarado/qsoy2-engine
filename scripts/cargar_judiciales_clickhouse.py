import pandas as pd
import clickhouse_connect
import os

FILE = "/mnt/pelis11min/proyectos_moved/QSoy2_data/ine_extraidos/baseDatosCandidatos_judicial.xls"
client = clickhouse_connect.get_client(host='localhost', username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''), database='qsoy')

if not os.path.exists(FILE):
    print(f"❌ No se encontró: {FILE}")
    exit()

print("📄 Leyendo base de datos de candidatos judiciales...")
df = pd.read_excel(FILE)
df.columns = [str(c).strip().upper() for c in df.columns]

# Crear tabla específica para judiciales
client.command('''
CREATE TABLE IF NOT EXISTS qsoy.candidatos_judiciales (
    nombre String, cargo String, entidad String, poder_postula String,
    sexo String, telefono String, correo String, redes String,
    escolaridad String, estatus String
) ENGINE = MergeTree() ORDER BY (entidad, cargo)
''')
client.command('TRUNCATE TABLE qsoy.candidatos_judiciales')

# Extraer solo las columnas limpias
df_clean = df[['NOMBRE_CANDIDATO', 'CARGO', 'ENTIDAD', 'PODER_POSTULA', 'SEXO', 'TELEFONO', 'CORREO_ELECTRONICO', 'REDES', 'ESCOLARIDAD', 'ESTATUS']].fillna('')
df_clean.columns = ['nombre', 'cargo', 'entidad', 'poder_postula', 'sexo', 'telefono', 'correo', 'redes', 'escolaridad', 'estatus']

print(f"📥 Insertando {len(df_clean)} candidatos judiciales...")
client.insert_df('qsoy.candidatos_judiciales', df_clean)
print("✅ Candidatos judiciales cargados en ClickHouse.")

# Buscar a los de Colima
print("\n=== CANDIDATOS JUDICIALES EN COLIMA ===")
res = client.query("SELECT nombre, cargo, sexo, telefono FROM qsoy.candidatos_judiciales WHERE entidad = 'COLIMA' LIMIT 20")
for row in res.result_rows:
    print(f"  {row[0]} | {row[1]} | {row[2]} | Tel: {row[3]}")
