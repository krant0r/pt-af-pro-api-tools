FROM python:slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# System deps (if later you need ca-cert bundles / curl etc., add here)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     ca-certificates \
#     && rm -rf /var/lib/apt/lists/*

RUN --mount=type=bind,source=requirements.txt,target=/requirements.txt \
    pip install --no-cache-dir -r requirements.txt && \
    addgroup --system app --gid 1000 && adduser --uid 1000 --system --home /home/app --group app

USER app
WORKDIR /home/app

EXPOSE 8000

# By default run FastAPI web app
CMD ["uvicorn", "modules.web_main:app", "--host", "0.0.0.0", "--port", "8000"]
