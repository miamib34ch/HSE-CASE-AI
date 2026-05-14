FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/backend

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends docker.io docker-compose && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY apps/backend ./apps/backend

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
