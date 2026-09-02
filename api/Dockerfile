# API FastAPI servida por uvicorn (proceso permanente en el VPS).
FROM python:3.12-slim

WORKDIR /app

# Dependencias primero (mejor cacheo de capas).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]==0.34.0"

COPY . .

ENV TZ=Europe/Madrid

EXPOSE 8000

# 1 worker: es una app de un solo usuario y en F3 el planificador de avisos
# correrá dentro de este mismo proceso (con varios se dispararía repetido).
CMD ["uvicorn", "index:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
