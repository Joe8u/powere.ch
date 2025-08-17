FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# 1) API-Requirements
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 2) App-Code
COPY apps/api/app ./app

# 3) powere-Paket ins Image bringen & installieren
COPY python /app/python
RUN pip install --no-cache-dir -e /app/python

# 4) Laufzeit-Config: Datenwurzel (per Volume mounten, siehe Compose)
ENV DATA_ROOT=/app/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]