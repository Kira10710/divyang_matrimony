# ======================================================================
# Divyang Matrimony — Backend Dockerfile
# ======================================================================
# Multi-stage build: install dependencies in builder, copy to slim runtime.
# Non-root user for security (Architecture Section 7.6).
# ======================================================================

# --- Builder stage ---
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# --- Runtime stage ---
FROM python:3.12-slim

# Security: run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, httpx; sys.exit(0 if httpx.get('http://localhost:8000/health', timeout=4).status_code == 200 else 1)"

# Run with uvicorn
# Forwarded headers are NOT trusted by uvicorn; the app resolves the client IP itself from
# TRUSTED_PROXY_HOPS (see app/core/dependencies.py). SIGTERM triggers a graceful stop.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--no-proxy-headers", "--no-server-header", "--timeout-graceful-shutdown", "25"]
