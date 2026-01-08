FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Meilisearch - download binary directly
RUN curl -L https://github.com/meilisearch/meilisearch/releases/download/v1.6.0/meilisearch-linux-amd64 -o /usr/local/bin/meilisearch && \
    chmod +x /usr/local/bin/meilisearch

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port 7860 (HF Spaces default)
EXPOSE 7860

# Run the application
CMD ["python", "app.py"]
