# Use official lightweight Python 3.12 slim image
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

# Copy project metadata and install Python dependencies
COPY pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source and frontend assets
COPY app/ /app/app/
COPY frontend/ /app/frontend/

# Expose standard Cloud Run port
EXPOSE 8080

# Run the FastAPI presentation bridge server
CMD ["python", "frontend/server.py"]
