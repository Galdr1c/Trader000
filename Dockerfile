# ─────────────────────────────────────────────────────────────────────
# SVTR Bot — Multi-stage Docker build
# ─────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

# Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create data/log dirs
RUN mkdir -p data logs

EXPOSE 8000

CMD ["python", "-m", "src.main"]
