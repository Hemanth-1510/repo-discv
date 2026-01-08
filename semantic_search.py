"""
Semantic search module for repository discovery
Uses sentence-transformers for vector similarity
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import time
import re


class SemanticExpander:
    """Vector similarity search with lazy loading and caching"""
    
    def __init__(self, embeddings_path='repo_embeddings.npz'):
        self._model = None
        self._query_cache = {}
        self._max_cache_size = 100
        
        # Load embeddings immediately (lightweight)
        print(f"Loading embeddings from {embeddings_path}...")
        data = np.load(embeddings_path)
        self.ids = data['ids']
        self.vectors = data['vectors']
        print(f"Loaded {len(self.ids)} repo embeddings ({self.vectors.shape[1]} dims)")
    
    @property
    def model(self):
        """Lazy load the model only when needed"""
        if self._model is None:
            print("Loading sentence-transformers model (first semantic query)...")
            start = time.time()
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            print(f"Model loaded in {time.time() - start:.2f}s")
        return self._model
    
    def find_similar(self, query_text: str, top_k: int = 50, min_similarity: float = 0.3) -> List[Dict]:
        """
        Find semantically similar repositories
        
        Args:
            query_text: Search query
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity threshold (0-1)
        
        Returns:
            List of {'id': repo_id, 'similarity': score}
        """
        
        # Check cache
        cache_key = (query_text, top_k, min_similarity)
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]
        
        # Encode query
        query_vec = self.model.encode(query_text, normalize_embeddings=True)
        
        # Cosine similarity (vectors already normalized)
        similarities = np.dot(self.vectors, query_vec)
        
        # Get top K above threshold
        valid_indices = np.where(similarities >= min_similarity)[0]
        valid_similarities = similarities[valid_indices]
        
        # Sort and take top K
        top_indices = valid_indices[np.argsort(valid_similarities)[-top_k:][::-1]]
        
        results = [
            {
                'id': str(self.ids[i]),
                'similarity': float(similarities[i])
            }
            for i in top_indices
        ]
        
        # Cache results
        if len(self._query_cache) >= self._max_cache_size:
            # Remove oldest entry
            self._query_cache.pop(next(iter(self._query_cache)))
        self._query_cache[cache_key] = results
        
        return results


def should_use_semantic_expansion(keyword_results: List[Dict], query: str) -> bool:
    """
    Determine if semantic expansion should be triggered
    
    Triggers when:
    - Low result count (< 20)  # Increased from 10
    - Abstract/conceptual query patterns (ALWAYS for these)
    - Weak top result (< 50)  # Increased from 30
    
    Never triggers for:
    - Exact repo names (contains '/')
    - Very popular search terms with many strong results
    """
    
    # Never for exact repo names
    if '/' in query:
        return False
    
    query_lower = query.lower()
    
    # ALWAYS trigger for abstract/conceptual patterns
    # These are the queries most likely to benefit from semantic search
    abstract_patterns = [
        r'\b(ui|framework|library|tool|system|platform)\b',
        r'\b(developer|backend|frontend|fullstack)\b',
        r'\b(monitoring|testing|security|deployment|devops)\b',
        r'\b(cli|terminal|command.?line|console|tui)\b',
        r'\b(data|analytics|visualization|dashboard)\b',
        r'\b(database|nosql|sql|storage)\b',
        r'\b(api|rest|graphql|grpc)\b',
    ]
    
    has_abstract_pattern = any(re.search(p, query_lower) for p in abstract_patterns)
    
    # ALWAYS trigger for abstract queries (no exceptions)
    if has_abstract_pattern:
        return True
    
    # For non-abstract queries, use stricter conditions
    # Trigger on low result count
    if len(keyword_results) < 20:  # Increased from 10
        return True
    
    # Trigger on weak relevance
    if keyword_results and keyword_results[0].get('custom_rank', 0) < 50:  # Increased from 30
        return True
    
    return False


# Global instance (lazy loaded on first use)
_semantic_expander = None


def get_semantic_expander(embeddings_path='repo_embeddings.npz') -> Optional[SemanticExpander]:
    """Get or create the global semantic expander instance"""
    global _semantic_expander
    
    if _semantic_expander is None:
        try:
            _semantic_expander = SemanticExpander(embeddings_path)
        except FileNotFoundError:
            print(f"Warning: Embeddings file not found at {embeddings_path}")
            print("Semantic search disabled. Run: python embeddings_generator.py")
            return None
    
    return _semantic_expander
