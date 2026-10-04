import os
import pandas as pd
import clickhouse_connect
import warnings
warnings.filterwarnings('ignore')

archivo = './datos_hidalgo/elecRetrns/datosBrutos/result-casillas-fed/fed2024all/casillas2024lonlat.csv'
print(f"📥 Leyendo coordenadas: {archivo}...")

df = pd.read_csv(archivo)

# Limpiar NaNs antes de convertir a tuplas
df = df.dropna(subset=['lat', 'lon', 'edon', 'seccion'])

# Crear una lista de tuplas con los datos exactos
datos = []
for idx, row in df.iterrows():
    datos.append((
        int(row['edon']),               # estado
        int(row['distrito_f']),         # distrito_f
        int(row['distrito_l']),         # distrito_l
        int(row['seccion']),            # seccion
        str(row['casilla']),            # tipo_casilla
        float(row['lat']),              # lat_casilla
        float(row['lon']),              # lon_casilla
        2024,                           # anio
        'INE_2024_LONLAT'               # fuente
    ))

print(f"🧹 Limpiando tabla por completo (TRUNCATE)...")
client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''), database='qsoy')
client.command("TRUNCATE TABLE qsoy.casillas_ubicacion")

print(f"🚀 Insertando {len(datos)} casillas...")
# Insertar pasando los datos y los nombres de las columnas por separado
client.insert(
    'casillas_ubicacion',
    datos,
    column_names=['estado', 'distrito_f', 'distrito_l', 'seccion', 'tipo_casilla', 'lat_casilla', 'lon_casilla', 'anio', 'fuente']
)

print("🎉 ¡Inserción real completada!")
