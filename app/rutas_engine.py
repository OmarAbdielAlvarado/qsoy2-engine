import requests

OSRM_URL = "http://localhost:5000"

def calcular_ruta_optima(curps_coords):
    if len(curps_coords) < 2:
        return {"error": "Se necesitan al menos 2 puntos para trazar una ruta."}
        
    coords_str = ";".join([f"{lon},{lat}" for lat, lon in curps_coords.values()])
    url = f"{OSRM_URL}/trip/v1/driving/{coords_str}?roundtrip=true&source=first&overview=full&geometries=geojson"
    
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 'Ok':
                ruta = data['trips'][0]
                orden = [wp['waypoint_index'] for wp in data['waypoints']]
                curps_ordenadas = [list(curps_coords.keys())[i] for i in orden]
                
                return {
                    "ruta_geojson": ruta['geometry'],
                    "distancia_km": round(ruta['distance'] / 1000, 2),
                    "duracion_min": round(ruta['duration'] / 60, 2),
                    "orden_visita": curps_ordenadas
                }
        return {"error": f"OSRM devolvió código {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}
