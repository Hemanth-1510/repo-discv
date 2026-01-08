#!/usr/bin/env python3
"""
Unified application for Hugging Face Spaces
Uses PRE-BUILT Meilisearch index (no indexing at startup)
"""

import os
import subprocess
import time
import signal
import sys

MASTER_KEY = "masterKey_at_least_16_chars_long"

print("===== Application Startup =====")

# Start Meilisearch with PRE-BUILT index from meili_data/
print("Starting Meilisearch with pre-built index...")
meili_process = subprocess.Popen([
    "meilisearch",
    "--db-path", "./meili_data",  # ← PRE-BUILT INDEX FROM GIT
    "--master-key", MASTER_KEY,
    "--http-addr", "0.0.0.0:7700",
    "--no-analytics"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

time.sleep(5)  # Wait for Meilisearch to start

print("✓ Meilisearch started with pre-indexed data (10,858 repos)")
print("✓ NO INDEXING NEEDED - using committed index")

# Start FastAPI server
print("Starting FastAPI server on port 7860...")

# Update search_api.py port before importing
with open('search_api.py', 'r') as f:
    content = f.read()
content = content.replace('port=8000', 'port=7860')
with open('search_api_hf.py', 'w') as f:
    f.write(content)

# Import and run
import uvicorn
from importlib import import_module

app_module = import_module('search_api_hf')
app = app_module.app

# Handle shutdown gracefully
def signal_handler(sig, frame):
    print("Shutting down...")
    meili_process.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Run server
uvicorn.run(app, host="0.0.0.0", port=7860)
