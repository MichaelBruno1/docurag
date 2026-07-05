FROM python:3.11-slim

# Install system dependencies for parsing, OCR (Tesseract + Portuguese pack), and PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    build-essential \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages (Docker cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code, entry points, and evaluation golden set
COPY src/ ./src/
COPY run.py worker.py ./
COPY tests/golden_set.json ./tests/golden_set.json

# Create data directories to match internal path layouts
RUN mkdir -p data/uploads data/qdrant data/logs

# Port exposed by the FastAPI server
EXPOSE 8000

# Default command starts the API
CMD ["python", "run.py"]
