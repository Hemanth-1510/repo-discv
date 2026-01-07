FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    meilisearch==0.31.1 \
    pydantic==2.10.0

# Copy application files
COPY search_api.py .
COPY indexer.py .
COPY meilisearch_config.json .

# Expose port
EXPOSE 8000

# Run API
CMD ["uvicorn", "search_api:app", "--host", "0.0.0.0", "--port", "8000"]
