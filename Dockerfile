# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install system deps needed by sentence-transformers / chromadb native libs
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (exclude secrets and data via .dockerignore)
COPY app/ app/
COPY indexer/ indexer/
COPY scripts/ scripts/

# Bake knowledge index into image (read-only at runtime).
# data/knowledge/ is committed to git — CI/CD can build without running indexer.
# data/vectordb/ is excluded (large binary, not used by any active tool).
COPY data/knowledge/ data/knowledge/

RUN mkdir -p data

# Run as non-root user
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
