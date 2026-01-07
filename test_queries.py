"""
Test runner for search queries
Executes test queries from test_queries.json and displays results
"""

import requests
import json
from typing import Dict, Any

API_URL = "http://localhost:8000/search"


def run_test_query(test: Dict[str, Any]):
    """Execute a single test query and display results"""
    print(f"\n{'='*80}")
    print(f"TEST: {test['name']}")
    print(f"{'='*80}")
    print(f"Query: '{test.get('query', '')}'")
    if 'filters' in test:
        print(f"Filters: {json.dumps(test['filters'], indent=2)}")
    print(f"Expected: {test.get('expected', 'N/A')}")
    print()
    
    # Build request
    request_data = {
        'query': test.get('query', ''),
        'page': 1,
        'per_page': test.get('per_page', 5)
    }
    
    if 'filters' in test:
        request_data['filters'] = test['filters']
    if 'sort_by' in test:
        request_data['sort_by'] = test['sort_by']
    if 'sort_order' in test:
        request_data['sort_order'] = test['sort_order']
    
    try:
        response = requests.post(API_URL, json=request_data, timeout=10)
        response.raise_for_status()
        
        results = response.json()
        
        print(f"✓ Found {results['total']} total results")
        print(f"✓ Processing time: {results['processing_time_ms']}ms")
        print(f"\nTop {len(results['results'])} results:")
        print(f"{'-'*80}")
        
        for i, repo in enumerate(results['results'], 1):
            print(f"\n{i}. {repo['nameWithOwner']} ({repo['stargazerCount']:,} ⭐)")
            print(f"   Language: {repo['primaryLanguage']}")
            if repo['topics']:
                print(f"   Topics: {', '.join(repo['topics'][:5])}")
            print(f"   Custom Rank: {repo['custom_rank']}")
            print(f"   Match: {repo['relevance_explanation']['query_match']}")
            print(f"   Factors: {', '.join(repo['relevance_explanation']['ranking_factors'][:3])}")
        
        print(f"\n{'-'*80}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Run all test queries"""
    print("="*80)
    print("MEILISEARCH REPOSITORY DISCOVERY - TEST RUNNER")
    print("="*80)
    
    # Check API health
    try:
        health = requests.get("http://localhost:8000/health", timeout=5)
        if health.status_code == 200:
            health_data = health.json()
            print(f"\n✓ API is healthy")
            print(f"✓ Indexed documents: {health_data.get('documents', 'unknown')}")
        else:
            print(f"\n✗ API returned status {health.status_code}")
            return
    except Exception as e:
        print(f"\n✗ Could not connect to API: {e}")
        print("Make sure the API is running: python search_api.py")
        return
    
    # Load test queries
    try:
        with open('test_queries.json', 'r') as f:
            tests = json.load(f)
    except FileNotFoundError:
        print("\n✗ test_queries.json not found")
        return
    
    # Run tests
    passed = 0
    failed = 0
    
    for test in tests:
        if run_test_query(test):
            passed += 1
        else:
            failed += 1
        
        input("\nPress Enter to continue to next test...")
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
