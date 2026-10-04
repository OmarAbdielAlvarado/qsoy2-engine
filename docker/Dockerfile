FROM python:3.11-slim

WORKDIR /app

# Copiar dependencias
COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Exponer puerto
EXPOSE 5002

# Comando para iniciar (Debe coincidir con la definición en docker-compose y main.py)
# Asumiendo que main.py usa 'app.main:app'
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5002"]
