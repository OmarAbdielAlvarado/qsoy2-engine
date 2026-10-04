# qsoy2-engine — Motor de analítica electoral (ClickHouse)
Columnar analytics en hardware de consumo. 100% local, sin nube.

## Estrella: simulador sintético determinista
Padrón sintético de **100,000,000 de filas exactas** (seed reproducible,
identidades 100% falsas). Generado y cargado en una sesión:
- ETL streaming: 826 s (~121K filas/s, HTTP, single-core CPU)
- uniqExact(curp): 99,999,991 → 99.999991% (paradoja del cumpleaños, medido)
- **GROUP BY estado sobre 100M filas: 225 ms**

## Benchmarks sobre datos públicos INE (procedencia SHA-256)
| Operación                     | Filas | Tiempo |
|-------------------------------|-------|--------|
| GROUP BY estado + sum(votos)  | 21.4M | 108 ms |
| GROUP BY top candidatos       | 21.4M | 247 ms |
| count()                       | 21.4M | 10 ms  |
| Participación por estado      | 516K  | 20 ms  |

Judicial Nacional: 21,398,987 registros · PREP 2024: 516,257 casillas (52.7M votos validados)

## Reproducir ($0)
    docker compose -f docker/docker-compose.yml up -d
    export CLICKHOUSE_PASSWORD=tu_clave_local
    python3 scripts/genera_sintetico.py --n 100000000 --cargar --tabla padron_sintetico
    time curl -s "http://localhost:8123/?user=default&password=$CLICKHOUSE_PASSWORD" \
      --data-binary "SELECT e, count() FROM qsoy.padron_sintetico GROUP BY e FORMAT PrettyCompact"

## Privacidad
Solo CÓDIGO en este repo. Cero datos reales, cero credenciales.
El generador produce identidades sintéticas sin correspondencia con
personas reales. Fuentes públicas oficiales trazadas con SHA-256.
