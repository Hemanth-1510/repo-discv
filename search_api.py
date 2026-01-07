"""
FastAPI Search API for Meilisearch Repository Discovery
Implements search, filtering, sorting, and explainable ranking
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import meilisearch
import math


app = FastAPI(title="Repository Discovery API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Meilisearch client
client = meilisearch.Client('http://localhost:7700', 'masterKey_at_least_16_chars_long')
index = client.index('repositories')


class SearchFilters(BaseModel):
    """Filters for repository search"""
    language: Optional[List[str]] = None
    min_stars: Optional[int] = None
    max_stars: Optional[int] = None
    min_last_updated: Optional[str] = None  # ISO date string
    is_active: Optional[bool] = None
    license: Optional[List[str]] = None
    owner_type: Optional[List[str]] = None  # Organization, User
    has_topics: Optional[bool] = None
    not_archived: Optional[bool] = True
    not_fork: Optional[bool] = None


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(default="", description="Search query string")
    filters: Optional[SearchFilters] = None
    sort_by: Optional[str] = Field(default="custom_rank", description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", description="Sort order: asc or desc")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=20, ge=1, le=100, description="Results per page")


class RelevanceExplanation(BaseModel):
    """Explanation of ranking decision"""
    query_match: str
    stars_score: float
    recency_score: float
    activity_score: float
    final_score: float
    ranking_factors: List[str]


class SearchResult(BaseModel):
    """Single search result with explainability"""
    id: str
    name: str
    nameWithOwner: str
    description: str
    url: str
    stargazerCount: int
    primaryLanguage: str
    topics: List[str]
    pushedAt: str
    is_active: bool
    custom_rank: float
    relevance_explanation: RelevanceExplanation


class SearchResponse(BaseModel):
    """Search response with metadata"""
    results: List[SearchResult]
    total: int
    page: int
    per_page: int
    total_pages: int
    processing_time_ms: int
    query: str


def build_filter_string(filters: Optional[SearchFilters]) -> str:
    """Build Meilisearch filter string from filters"""
    if not filters:
        return ""
    
    conditions = []
    
    # Language filter
    if filters.language:
        lang_conditions = [f"primaryLanguage = '{lang}'" for lang in filters.language]
        if len(lang_conditions) > 1:
            conditions.append(f"({' OR '.join(lang_conditions)})")
        else:
            conditions.extend(lang_conditions)
    
    # Stars range
    if filters.min_stars is not None:
        conditions.append(f"stargazerCount >= {filters.min_stars}")
    if filters.max_stars is not None:
        conditions.append(f"stargazerCount <= {filters.max_stars}")
    
    # Last updated (active repositories)
    if filters.min_last_updated:
        conditions.append(f"pushedAt >= '{filters.min_last_updated}'")
    
    if filters.is_active is not None:
        conditions.append(f"is_active = {str(filters.is_active).lower()}")
    
    # License filter
    if filters.license:
        lic_conditions = [f"license_spdxId = '{lic}'" for lic in filters.license]
        if len(lic_conditions) > 1:
            conditions.append(f"({' OR '.join(lic_conditions)})")
        else:
            conditions.extend(lic_conditions)
    
    # Owner type
    if filters.owner_type:
        owner_conditions = [f"owner_type = '{ot}'" for ot in filters.owner_type]
        if len(owner_conditions) > 1:
            conditions.append(f"({' OR '.join(owner_conditions)})")
        else:
            conditions.extend(owner_conditions)
    
    # Archived filter
    if filters.not_archived:
        conditions.append(f"isArchived = false")
    
    # Fork filter
    if filters.not_fork:
        conditions.append(f"isFork = false")
    
    return " AND ".join(conditions)


def explain_ranking(result: Dict[str, Any], query: str) -> RelevanceExplanation:
    """Generate explanation for ranking decision"""
    
    stars = result.get('stargazerCount', 0)
    stars_score = min(100, math.log10(stars + 1) * 20)
    
    # Simple recency calculation
    recency_days = result.get('recency_days', 99999)
    recency_score = 100 * math.exp(-recency_days / 365.0)
    
    # Activity score
    issues = result.get('issuesCount', 0) or 0
    prs = result.get('pullRequestsCount', 0) or 0
    activity_score = min(100, (issues + prs) / 50)
    
    final_score = result.get('custom_rank', 0)
    
    # Determine ranking factors
    factors = []
    if stars > 10000:
        factors.append(f"High star count ({stars:,} stars)")
    elif stars > 1000:
        factors.append(f"Popular repository ({stars:,} stars)")
    
    if recency_days < 30:
        factors.append("Recently updated (within 30 days)")
    elif recency_days < 365:
        factors.append("Active repository (updated this year)")
    
    if result.get('topics') and len(result['topics']) > 0:
        factors.append(f"Well-tagged ({len(result['topics'])} topics)")
    
    if activity_score > 50:
        factors.append("High community engagement")
    
    # Topic/description match
    query_lower = query.lower()
    description = (result.get('description') or '').lower()
    topics = [t.lower() for t in result.get('topics', [])]
    name = result.get('name', '').lower()
    
    match_explanation = []
    if query and query_lower in name:
        match_explanation.append(f"name match: '{query}'")
    if query and any(query_lower in topic for topic in topics):
        match_explanation.append(f"topic match: '{query}'")
    if query and query_lower in description:
        match_explanation.append(f"description contains '{query}'")
    
    if not match_explanation and query:
        match_explanation.append("General relevance based on searchable fields")
    elif not query:
        match_explanation.append("Ranked by custom score (no query)")
    
    return RelevanceExplanation(
        query_match=" | ".join(match_explanation),
        stars_score=round(stars_score, 2),
        recency_score=round(recency_score, 2),
        activity_score=round(activity_score, 2),
        final_score=round(final_score, 2),
        ranking_factors=factors if factors else ["Standard relevance ranking"]
    )


@app.post("/search", response_model=SearchResponse)
async def search_repositories(request: SearchRequest):
    """
    Search repositories with filters and explainable ranking
    
    - **query**: Search terms (searches name, description, topics, language)
    - **filters**: Optional filters for language, stars, activity, etc.
    - **sort_by**: Field to sort by (default: custom_rank)
    - **sort_order**: asc or desc (default: desc)
    - **page**: Page number starting from 1
    - **per_page**: Results per page (max 100)
    """
    
    # Build filter string
    filter_str = build_filter_string(request.filters)
    
    # Calculate offset
    offset = (request.page - 1) * request.per_page
    
    # Build sort string
    sort_field = request.sort_by if request.sort_by else "custom_rank"
    sort_order = request.sort_order if request.sort_order else "desc"
    sort_str = f"{sort_field}:{sort_order}"
    
    try:
        # Execute search
        search_params = {
            'limit': request.per_page,
            'offset': offset,
            'sort': [sort_str],
        }
        
        if filter_str:
            search_params['filter'] = filter_str
        
        results = index.search(request.query, search_params)
        
        # Transform results with explainability
        search_results = []
        for hit in results['hits']:
            explanation = explain_ranking(hit, request.query)
            
            search_results.append(SearchResult(
                id=hit['id'],
                name=hit.get('name', ''),
                nameWithOwner=hit.get('nameWithOwner', ''),
                description=hit.get('description', '') or '',
                url=hit.get('url', ''),
                stargazerCount=hit.get('stargazerCount', 0),
                primaryLanguage=hit.get('primaryLanguage', 'Unknown'),
                topics=hit.get('topics', []),
                pushedAt=hit.get('pushedAt', ''),
                is_active=hit.get('is_active', False),
                custom_rank=hit.get('custom_rank', 0),
                relevance_explanation=explanation
            ))
        
        total = min(results.get('estimatedTotalHits', 0), 10000)
        total_pages = (total + request.per_page - 1) // request.per_page
        
        return SearchResponse(
            results=search_results,
            total=total,
            page=request.page,
            per_page=request.per_page,
            total_pages=total_pages,
            processing_time_ms=results.get('processingTimeMs', 0),
            query=request.query
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        stats = index.get_stats()
        return {
            "status": "healthy",
            "documents": stats.number_of_documents,
            "indexing": stats.is_indexing
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.get("/stats")
async def get_stats():
    """Get index statistics"""
    try:
        stats = index.get_stats()
        return {
            "total_documents": stats.number_of_documents,
            "is_indexing": stats.is_indexing,
            "field_distribution": stats.field_distribution
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
