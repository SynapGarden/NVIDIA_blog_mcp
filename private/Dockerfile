# Use the official Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code from private/ folder
COPY private/main.py ./
COPY private/gcs_utils.py ./
COPY private/html_cleaner.py ./
COPY private/rag_ingest.py ./
COPY private/rss_fetcher.py ./
COPY private/vector_search_ingest.py ./

# Copy config from mcp/ folder (needed by main.py)
COPY mcp/config.py ./

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "main.py"]

