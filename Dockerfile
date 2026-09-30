# Use official lightweight Python 3.12 slim image
# Dependencies are installed via uv --frozen to pin exact versions from uv.lock
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for reproducible dependency installation
RUN pip install --no-cache-dir uv

# Copy lock files first (better layer caching — only re-runs on dep changes)
COPY pyproject.toml uv.lock /app/

# Install dependencies using the exact locked versions (no dev extras)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source and frontend assets
COPY app/ /app/app/
COPY frontend/ /app/frontend/

# Expose standard Cloud Run port
EXPOSE 8080

# Run via uv so the locked virtualenv is activated automatically
CMD ["uv", "run", "python", "frontend/server.py"]
