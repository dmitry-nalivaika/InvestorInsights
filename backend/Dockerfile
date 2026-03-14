# filepath: backend/Dockerfile
# ── Stage 1: Build ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies for PyMuPDF and asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libffi-dev \
        libmupdf-dev \
        mupdf-tools && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.12-slim

# Runtime dependencies for PyMuPDF and asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libmupdf-dev \
        mupdf-tools \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
WORKDIR /app
COPY . .

# Remove dev files not needed at runtime
RUN rm -rf tests/ requirements-dev.txt .pytest_cache/ __pycache__/

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
