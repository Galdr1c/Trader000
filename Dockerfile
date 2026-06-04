# ─────────────────────────────────────────────────────────────────────
# SVTR Bot — Multi-stage Docker build (Phase 4: Production hardened)
# ─────────────────────────────────────────────────────────────────────

# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime (minimal attack surface)
FROM python:3.12-slim AS runtime

# Security: non-root user
RUN groupadd -r svtr && useradd -r -g svtr -d /app -s /sbin/nologin svtr

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy app code
COPY . .

# Create directories with proper ownership
RUN mkdir -p data logs && chown -R svtr:svtr /app

# Switch to non-root user
USER svtr

EXPOSE 8000

# Health check built into image
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "src.main"]
