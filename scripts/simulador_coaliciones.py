import os
import clickhouse_connect

# Configuración de ClickHouse
client = clickhouse_connect.get_client(host='localhost', port='8123', username='default', password=os.environ.get('CLICKHOUSE_PASSWORD',''))

def simular_escenario(estado_id, municipio_id, voto_casa, partidos_seleccionados):
    """
    Simula el escenario electoral aplicando la regla de canibalización.
    partidos_seleccionados: Lista de strings, ej. ['PAN', 'PRI', 'PRD']
    """
    print(f"\n📊 SIMULANDO ESCENARIO EN ESTADO {estado_id}, MUNICIPIO {municipio_id}...")
    print(f"Voto en Casa: {voto_casa} | Partidos: {', '.join(partidos_seleccionados)}")
    
    # 1. Obtener el piso histórico de los partidos seleccionados en el municipio
    partidos_str = "', '".join(partidos_seleccionados)
    query_votos = f"""
    SELECT SUM(votos) 
    FROM qsoy.resultados_electorales 
    WHERE estado = '{estado_id}' AND municipio = {municipio_id} 
    AND partido IN ('{partidos_str}')
    """
    piso_historico = client.query(query_votos).result_rows[0][0] or 0
    print(f"Piso histórico combinado ({', '.join(partidos_seleccionados)}): {piso_historico:,} votos")
    
    # 2. Aplicar Regla de Canibalización (10% si es coalición de 2 o más)
    if len(partidos_seleccionados) >= 2:
        factor_canibalizacion = 0.90
        print(f"⚠️ Canibalización aplicada (Coalición de {len(partidos_seleccionados)} partidos): -10%")
    else:
        factor_canibalizacion = 1.0
        
    voto_proyectado = int((voto_casa + piso_historico) * factor_canibalizacion)
    print(f"Voto Proyectado Total: {voto_proyectado:,} votos")
    
    # 3. Consultar la ley de regiduría (Plan B) desde la nueva tabla
    query_ley = f"SELECT umbral_porcentaje, base_calculo, articulo_legal FROM qsoy.leyes_regidurias_detalle WHERE estado_id = {estado_id}"
    ley = client.query(query_ley).result_rows
    
    if ley:
        umbral, base_calculo, articulo = ley[0]
        # Para simplificar, asumimos que el total de votos válidos es el doble del piso + voto casa
        total_validos_estimado = (piso_historico + voto_casa) * 2 
        votos_necesarios_regiduria = int(total_validos_estimado * (umbral / 100))
        
        print(f"\n⚖️ ANÁLISIS LEGAL (Plan B):")
        print(f"Según el {articulo}:")
        print(f"Se requiere el {umbral}% de {base_calculo}.")
        print(f"Votos necesarios para Regiduría: ~{votos_necesarios_regiduria:,} votos")
        
        if voto_proyectado >= votos_necesarios_regiduria:
            print("✅ RESULTADO: El candidato ASEGURARÍA una Regiduría.")
        else:
            print("❌ RESULTADO: El candidato NO alcanzaría la Regiduría por este camino.")
            
    return voto_proyectado

# === PRUEBA DEL SIMULADOR (CASO LUIS VALENZUELA) ===
if __name__ == "__main__":
    # Luis va por la coalición PAN+PRI en San Nicolás (Municipio 47)
    simular_escenario('19', 47, 350, ['PAN', 'PRI'])
