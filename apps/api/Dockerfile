FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# 1) API-Requirements
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 2) App-Code
COPY apps/api/app ./app

# 3) API-Code + ai_guide
COPY ai_guide ./ai_guide

# 4) Steps-Code (für Code-Karten in der Knowledge Base)
COPY steps ./steps

# 5) Laufzeit-Config: Datenwurzel (per Volume mounten, siehe Compose)
ENV DATA_ROOT=/app/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

