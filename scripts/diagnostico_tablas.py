import os
import clickhouse_connect

client = clickhouse_connect.get_client(host='localhost', username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''), database='qsoy')

print("=== ESQUEMA Y EJEMPLOS: qsoy.candidatos ===")
print("\nColumnas:")
cols = client.query("DESCRIBE TABLE qsoy.candidatos")
for c in cols.result_rows:
    print(f"  - {c[0]} ({c[1]})")

print("\nEjemplo de datos (Ayuntamiento 2021):")
data = client.query("SELECT * FROM qsoy.candidatos WHERE tipo_eleccion = 'AYUNTAMIENTO' AND anio = 2021 LIMIT 2")
for row in data.result_rows:
    print(row)

print("\n" + "-"*80 + "\n")

print("=== ESQUEMA Y EJEMPLOS: qsoy.resultados_electorales ===")
print("\nColumnas:")
cols2 = client.query("DESCRIBE TABLE qsoy.resultados_electorales")
for c in cols2.result_rows:
    print(f"  - {c[0]} ({c[1]})")

print("\nEjemplo de datos:")
try:
    # Intentamos traer 2 filas de cualquier año
    data2 = client.query("SELECT * FROM qsoy.resultados_electorales LIMIT 2")
    for row in data2.result_rows:
        print(row)
except Exception as e:
    print(f"Error al traer ejemplo: {e}")

