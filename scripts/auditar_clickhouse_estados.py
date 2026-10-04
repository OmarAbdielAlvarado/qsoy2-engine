import os
import clickhouse_connect

client = clickhouse_connect.get_client(host='localhost', username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''), database='qsoy')

print("📊 AUDITORÍA DE RESULTADOS ELECTORALES EN CLICKHOUSE\n")
print("Mostrando filas y votos totales por Estado y Año:\n")

query = """
SELECT 
    estado, 
    anio, 
    count() as filas, 
    sum(votos) as total_votos
FROM qsoy.resultados_electorales
GROUP BY estado, anio
ORDER BY estado ASC, anio ASC
"""

try:
    res = client.query(query)
    if res.result_rows:
        current_estado = None
        for row in res.result_rows:
            estado, anio, filas, votos = row
            if estado != current_estado:
                print(f"\n=== ESTADO {estado} ===")
                current_estado = estado
            print(f"  Año {anio}: {filas:,} filas | {votos:,} votos")
    else:
        print("No se encontraron datos.")
except Exception as e:
    print(f"❌ Error: {e}")
