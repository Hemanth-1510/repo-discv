#!/bin/bash

# Setup script for Meilisearch Repository Discovery System
# This script initializes Meilisearch and indexes the repository data

set -e

echo "=== Meilisearch Repository Discovery System Setup ==="
echo

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# Check if CSV file exists
if [ ! -f "enriched_final.csv" ]; then
    echo "Error: enriched_final.csv not found in current directory"
    exit 1
fi

echo "Step 1: Starting Meilisearch via Docker Compose..."
docker-compose up -d meilisearch

echo "Waiting for Meilisearch to be ready..."
sleep 10

# Wait for Meilisearch health check
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://localhost:7700/health > /dev/null 2>&1; then
        echo "✓ Meilisearch is ready"
        break
    fi
    echo "Waiting for Meilisearch... ($((attempt+1))/$max_attempts)"
    sleep 2
    attempt=$((attempt+1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "Error: Meilisearch failed to start"
    exit 1
fi

echo
echo "Step 2: Installing Python dependencies..."
pip install -r requirements.txt

echo
echo "Step 3: Indexing repositories from enriched_final.csv..."
python indexer.py --csv enriched_final.csv --host http://localhost:7700 --key masterKey

echo
echo "Step 4: Verifying index..."
INDEX_STATS=$(curl -s http://localhost:7700/indexes/repositories/stats -H "Authorization: Bearer masterKey")
DOCUMENT_COUNT=$(echo $INDEX_STATS | grep -o '"numberOfDocuments":[0-9]*' | grep -o '[0-9]*')
echo "✓ Indexed $DOCUMENT_COUNT documents"

echo
echo "=== Setup Complete ==="
echo
echo "Meilisearch is running at: http://localhost:7700"
echo "Meilisearch Dashboard: http://localhost:7700"
echo
echo "To start the search API:"
echo "  python search_api.py"
echo "  OR"
echo "  docker-compose up search-api"
echo
echo "API Documentation will be available at: http://localhost:8000/docs"
echo
echo "To stop services:"
echo "  docker-compose down"
