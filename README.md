<<<<<<< HEAD
# Repository Search

Search through 10,858 GitHub repositories using Meilisearch. No AI, no paid APIs.

## What You Get

- Search by name, description, topics, language
- Filter by language, stars, activity status
- Sort by relevance, stars, or update date
- See why each result ranked where it did
- Web UI at `index.html`
- API at `http://localhost:8000`

## Quick Start

**1. Start Meilisearch**

Make sure Docker Desktop is running, then:

```powershell
docker-compose up -d meilisearch
```

**2. Install Python packages**

```powershell
pip install fastapi uvicorn meilisearch requests
```

**3. Index your data**

```powershell
python indexer.py --key masterKey_at_least_16_chars_long
```

This takes about 45 seconds. You'll see:
```
Indexing complete!
Total documents indexed: 10858
```

**4. Use the web UI**

Just open `index.html` in your browser. Done.

**OR start the API server:**

```powershell
python search_api.py
```

Then go to `http://localhost:8000/docs` for the API interface.

## How It Works

**Ranking Formula:**
```
score = (stars × 0.4) + (recency × 0.3) + (activity × 0.2) + (topics × 0.1)
```

- Stars score is logarithmic (so mega-repos don't dominate)
- Recency decays exponentially from last update
- Activity based on issues + PRs
- Repos not updated in 2+ years get 50% penalty

**Synonyms:**
- `backend` → server, api, microservice, rest, graphql
- `frontend` → ui, interface, client, web app, dashboard
- `security` → auth, encryption, vulnerability
- `ml` → machine learning, tensorflow, pytorch

## Files

- `enriched_final.csv` - Your 10,858 repos
- `indexer.py` - Reads CSV, computes scores, indexes to Meilisearch
- `search_api.py` - FastAPI server
- `index.html` - Web UI (single file, no build needed)
- `meilisearch_config.json` - Search settings
- `docker-compose.yml` - Meilisearch container config

## Using the API

```python
import requests

# Search
r = requests.post('http://localhost:8000/search', json={
    'query': 'python web framework',
    'filters': {
        'language': ['Python'],
        'min_stars': 1000,
        'is_active': True
    },
    'per_page': 10
})

results = r.json()
for repo in results['results']:
    print(f"{repo['nameWithOwner']} - {repo['stargazerCount']} stars")
    print(f"Score: {repo['custom_rank']}")
    print(f"Why: {repo['relevance_explanation']['ranking_factors']}")
```

## Filters

**By language:**
```json
{"language": ["Python", "Go", "Rust"]}
```

**By stars:**
```json
{"min_stars": 1000, "max_stars": 50000}
```

**By activity:**
```json
{"is_active": true}
```

**By owner type:**
```json
{"owner_type": ["Organization"]}
```

**Exclude archived/forks:**
```json
{"not_archived": true, "not_fork": true}
```

## Sorting

- `custom_rank` - Best match (default)
- `stargazerCount` - Most stars
- `pushedAt` - Recently updated
- `createdAt` - Newest

## Troubleshooting

**Docker won't start:**
- Make sure Docker Desktop is running
- Check `docker version` works

**No results after indexing:**
```powershell
# Check if it's actually indexed
curl.exe http://localhost:7700/indexes/repositories/stats -H "Authorization: Bearer masterKey_at_least_16_chars_long"
```

**API won't connect:**
- Make sure `python search_api.py` is running
- Check http://localhost:8000/health

**Start over:**
```powershell
docker-compose down -v
docker-compose up -d meilisearch
python indexer.py --key masterKey_at_least_16_chars_long
```

## Performance

- 10,858 documents indexed
- ~18 MB index size
- < 50ms search latency
- 1,000 repos per batch during indexing

## Stopping

```powershell
# Stop API (Ctrl+C in the terminal)
# Stop Meilisearch
docker-compose down
```

## That's It

Search works. UI works. API works. No dependencies beyond what's in `requirements.txt`.
=======
# Demos

1. Resume matching: https://github.com/deepklarity/demos/tree/resume-matching
>>>>>>> 0ccffb3b16ef9b91b273775798109e6cd131712f
