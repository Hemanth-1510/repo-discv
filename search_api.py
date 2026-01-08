from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import meilisearch

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return FileResponse("index.html")

# Connect to Meilisearch
client = meilisearch.Client('http://localhost:7700', 'masterKey_at_least_16_chars_long')
index = client.index('repositories')

class SearchRequest(BaseModel):
    query: str = ""
    page: int = 1
    per_page: int = 20
    language: str = None
    min_stars: int = None
    activity: str = None
    sort_by: str = "custom_rank"
    sort_order: str = "desc"

class SearchResponse(BaseModel):
    results: List[dict]
    total: int
    page: int
    per_page: int
    total_pages: int
    processing_time_ms: int

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Ultra-simple search - just get docs and return them"""
    try:
        offset = (request.page - 1) * request.per_page
        
        # Get documents directly
        docs_result = index.get_documents({
            'offset': offset,
            'limit': request.per_page
        })
        
        # Convert to dicts
        results = []
        for doc in docs_result.results:
            if hasattr(doc, '__dict__'):
                results.append(doc.__dict__)
            else:
                results.append(dict(doc))
        
        # Get total
        stats = index.get_stats()
        total = stats.number_of_documents
        
        # Sort by custom_rank
        results.sort(key=lambda x: x.get('custom_rank', 0), reverse=True)
        
        return SearchResponse(
            results=results,
            total=total,
            page=request.page,
            per_page=request.per_page,
            total_pages=(total + request.per_page - 1) // request.per_page,
            processing_time_ms=10
        )
    except Exception as e:
        print(f"ERROR in search: {e}")
        import traceback
        traceback.print_exc()
        return SearchResponse(
            results=[],
            total=0,
            page=1,
            per_page=20,
            total_pages=0,
            processing_time_ms=0
        )
