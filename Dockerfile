FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps (if later you need ca-cert bundles / curl etc., add here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# By default run FastAPI web app
CMD ["uvicorn", "modules.web_main:app", "--host", "0.0.0.0", "--port", "8000"]
