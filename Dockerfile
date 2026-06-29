# Signal Forge v2 — Dual Gradio + FastAPI
# Build target: "ui" (Gradio) or "api" (FastAPI)
# Usage: docker build --target ui -t signal-forge-ui .
#        docker build --target api -t signal-forge-api .

FROM python:3.12-slim AS base

WORKDIR /app

# System deps for sqlite3, curl (healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data/outputs dirs exist
RUN mkdir -p /app/data /app/outputs/saved_decodes

# ─── Gradio UI target ──────────────────────────────────────────────────────
FROM base AS ui
EXPOSE 7860
ENV GRADIO_SERVER_NAME=0.0.0.0
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1
CMD ["python", "app_v2.py"]

# ─── FastAPI target ─────────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
