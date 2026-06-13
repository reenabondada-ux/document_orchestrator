FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first (needed for editable install)
COPY pyproject.toml ./
COPY README.md ./README.md
COPY mainframe_doc_orchestrator ./mainframe_doc_orchestrator

# Install Python dependencies from pyproject.toml
RUN pip install --upgrade pip && \
    pip install -e .

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH=/app

EXPOSE 8010

CMD ["uvicorn", "mainframe_doc_orchestrator.api.app:app", "--host", "0.0.0.0", "--port", "8010"]
