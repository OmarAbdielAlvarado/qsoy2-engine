import random

def calcular_ocean(candidato, partido, estado, anio):
    """
    Motor heurístico para estimar el perfil OCEAN de un candidato.
    Devuelve un diccionario con los 5 rasgos en porcentaje (0-100).
    """
    # Semilla basada en el nombre para que el perfil sea consistente
    seed = sum(ord(c) for c in candidato) + sum(ord(c) for c in partido)
    random.seed(seed)
    
    # Heurísticas básicas por partido
    if partido in ['MORENA', 'PT', 'PVEM']:
        apertura = random.randint(55, 85)  # Más progresista
        responsabilidad = random.randint(40, 60)
        extraversion = random.randint(65, 90)
        amabilidad = random.randint(40, 65)
        estabilidad = random.randint(30, 55)
    elif partido in ['PAN', 'PRI']:
        apertura = random.randint(30, 55)  # Más conservador
        responsabilidad = random.randint(65, 85)
        extraversion = random.randint(55, 75)
        amabilidad = random.randint(50, 70)
        estabilidad = random.randint(60, 80)
    elif partido in ['MC', 'PRD']:
        apertura = random.randint(50, 70)
        responsabilidad = random.randint(50, 70)
        extraversion = random.randint(60, 80)
        amabilidad = random.randint(55, 75)
        estabilidad = random.randint(45, 65)
    else:
        # Independientes u otros
        apertura = random.randint(40, 80)
        responsabilidad = random.randint(40, 80)
        extraversion = random.randint(40, 80)
        amabilidad = random.randint(40, 80)
        estabilidad = random.randint(40, 80)
    
    return {
        "Apertura": apertura,
        "Responsabilidad": responsabilidad,
        "Extraversion": extraversion,
        "Amabilidad": amabilidad,
        "Estabilidad": estabilidad
    }

def buscar_redes_sociales(candidato):
    """
    Genera búsquedas directas en redes sociales para el candidato.
    """
    nombre_limpio = candidato.replace(' ', '%20')
    return [
        {"plataforma": "X (Twitter)", "url": f"https://twitter.com/search?q={nombre_limpio}&src=typed_query"},
        {"plataforma": "Facebook", "url": f"https://www.facebook.com/search/top?q={nombre_limpio}"},
        {"plataforma": "Instagram", "url": f"https://www.instagram.com/explore/tags/{nombre_limpio.replace('%20', '')}/"},
        {"plataforma": "Google News", "url": f"https://news.google.com/search?q={nombre_limpio}%20politico&hl=es"}
    ]
