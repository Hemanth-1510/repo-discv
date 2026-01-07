#!/usr/bin/env python3
"""
Repository Indexer for Meilisearch
Reads enriched_final.csv and indexes repositories with computed ranking fields
"""

import csv
import json
import math
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
import meilisearch


def parse_topics(topics_str: str) -> List[str]:
    """Parse topics from CSV string format"""
    if not topics_str or topics_str == '':
        return []
    # Topics are stored as comma-separated quoted strings
    topics = [t.strip().strip('"').strip("'") for t in topics_str.split(',')]
    return [t for t in topics if t]


def calculate_custom_rank(repo: Dict[str, Any], now: datetime) -> float:
    """
    Calculate deterministic ranking score
    Formula: (stars_score × 0.4) + (recency_score × 0.3) + (activity_score × 0.2) + (topic_bonus × 0.1)
    """
    # Stars score (logarithmic to prevent mega-repos dominating)
    stars = repo.get('stargazerCount', 0) or 0
    stars_score = min(100, math.log10(stars + 1) * 20)
    
    # Recency score (exponential decay from last push)
    pushed_at_str = repo.get('pushedAt', '')
    if pushed_at_str:
        try:
            pushed_at = datetime.fromisoformat(pushed_at_str.replace('Z', '+00:00'))
            days_old = (now - pushed_at).days
            recency_score = 100 * math.exp(-days_old / 365.0)
        except (ValueError, AttributeError):
            recency_score = 0
    else:
        recency_score = 0
    
    # Activity score (normalized from issues + PRs)
    issues = repo.get('issuesCount', 0) or 0
    prs = repo.get('pullRequestsCount', 0) or 0
    activity_metric = issues + prs
    activity_score = min(100, activity_metric / 50)
    
    # Topic bonus (repos with topics get small boost)
    topic_bonus = 20 if repo.get('topics') and len(repo['topics']) > 0 else 0
    
    # Inactivity penalty (repos not updated in 2+ years)
    penalty = 0.5 if (pushed_at_str and days_old > 730) else 1.0
    
    final_score = (
        stars_score * 0.4 +
        recency_score * 0.3 +
        activity_score * 0.2 +
        topic_bonus * 0.1
    ) * penalty
    
    return round(final_score, 2)


def transform_repo_for_index(row: Dict[str, str], now: datetime) -> Dict[str, Any]:
    """Transform CSV row into Meilisearch document"""
    
    # Parse numeric fields
    stars = int(row['stargazerCount']) if row.get('stargazerCount') else 0
    forks = int(row['forkCount']) if row.get('forkCount') else 0
    issues = int(row['issuesCount']) if row.get('issuesCount') else 0
    prs = int(row['pullRequestsCount']) if row.get('pullRequestsCount') else 0
    watchers = int(row['watchersCount']) if row.get('watchersCount') else 0
    
    # Parse topics
    topics = parse_topics(row.get('topics', ''))
    
    # Check if active (pushed within last 2 years)
    pushed_at = row.get('pushedAt', '')
    is_active = False
    if pushed_at:
        try:
            pushed_date = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
            days_since_push = (now - pushed_date).days
            is_active = days_since_push < 730
        except:
            pass
    
    # Build document
    # Use nameWithOwner as ID (Meilisearch only allows alphanumeric, hyphens, underscores)
    import re
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', row.get('nameWithOwner', ''))
    
    doc = {
        'id': safe_id,  # Sanitized ID
        'github_id': row['id'],  # Keep original as field
        'name': row.get('name', ''),
        'nameWithOwner': row.get('nameWithOwner', ''),
        'url': row.get('url', ''),
        'description': row.get('description', '') or '',
        'stargazerCount': stars,
        'forkCount': forks,
        'isFork': row.get('isFork', 'False') == 'True',
        'createdAt': row.get('createdAt', ''),
        'pushedAt': pushed_at,
        'primaryLanguage': row.get('primaryLanguage', '') or 'Unknown',
        'homepageUrl': row.get('homepageUrl', ''),
        'isArchived': row.get('isArchived', 'False') == 'True',
        'hasIssuesEnabled': row.get('hasIssuesEnabled', 'False') == 'True',
        'watchersCount': watchers,
        'issuesCount': issues,
        'pullRequestsCount': prs,
        'license_spdxId': row.get('license_spdxId', ''),
        'license_name': row.get('license_name', ''),
        'topics': topics,
        'owner_type': row.get('owner_type', ''),
        'owner_login': row.get('owner_login', ''),
        'owner_location': row.get('owner_location', ''),
        'lang1_name': row.get('lang1_name', ''),
        'lang2_name': row.get('lang2_name', ''),
        'lang3_name': row.get('lang3_name', ''),
        'is_active': is_active,
    }
    
    # Calculate custom ranking score
    doc['custom_rank'] = calculate_custom_rank(doc, now)
    
    # Normalized stars (for filtering)
    doc['stars_normalized'] = min(100, math.log10(stars + 1) * 20)
    
    # Days since last update
    if pushed_at:
        try:
            pushed_date = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
            doc['recency_days'] = (now - pushed_date).days
        except:
            doc['recency_days'] = 99999
    else:
        doc['recency_days'] = 99999
    
    return doc


def index_repositories(csv_path: str, host: str = 'http://localhost:7700', api_key: str = 'masterKey', index_name: str = 'repositories', batch_size: int = 1000):
    """Read CSV and index repositories into Meilisearch"""
    
    print(f"Connecting to Meilisearch at {host}...")
    client = meilisearch.Client(host, api_key)
    
    # Create or get index
    try:
        index = client.get_index(index_name)
        print(f"Using existing index: {index_name}")
    except:
        print(f"Creating new index: {index_name}")
        task = client.create_index(index_name, {'primaryKey': 'id'})
        # Wait for index creation to complete (async operation)
        print("Waiting for index creation...")
        time.sleep(3)
        index = client.get_index(index_name)
    
    # Load and apply configuration
    print("Applying index configuration...")
    with open('meilisearch_config.json', 'r') as f:
        config = json.load(f)
    
    # Apply settings using update_settings (works with meilisearch 0.38.0)
    settings = {
        'filterableAttributes': config['filterableAttributes'],
        'sortableAttributes': config['sortableAttributes'],
        'searchableAttributes': config['searchableAttributes'],
        'rankingRules': config['rankingRules'],
        'stopWords': config['stopWords'],
        'synonyms': config['synonyms'],
        'typoTolerance': config['typoTolerance'],
        'pagination': config['pagination']
    }
    
    index.update_settings(settings)
    print("Configuration applied successfully")
    time.sleep(2)  # Wait for settings to be applied
    
    # Read and index CSV
    print(f"Reading repositories from {csv_path}...")
    repositories = []
    now = datetime.now(timezone.utc)
    task_ids = []
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            try:
                doc = transform_repo_for_index(row, now)
                repositories.append(doc)
                
                # Index in batches
                if len(repositories) >= batch_size:
                    print(f"Indexing batch of {len(repositories)} repositories...")
                    task_info = index.add_documents(repositories)
                    task_ids.append(task_info.task_uid)
                    repositories = []
                    
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
    
    # Index remaining repositories
    if repositories:
        print(f"Indexing final batch of {len(repositories)} repositories...")
        task_info = index.add_documents(repositories)
        task_ids.append(task_info.task_uid)
    
    # Wait for all indexing tasks to complete
    print(f"Waiting for {len(task_ids)} indexing tasks to complete...")
    for task_id in task_ids:
        # Wait for each task
        task = client.wait_for_task(task_id, timeout_in_ms=60000)
        if task.status == 'failed':
            print(f"Task {task_id} failed: {task.error}")
    
    time.sleep(2)  # Additional buffer
    
    # Get stats
    stats = index.get_stats()
    print(f"\nIndexing complete!")
    print(f"Total documents indexed: {stats.number_of_documents}")
    print(f"Index is ready for search at: {host}/indexes/{index_name}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Index GitHub repositories into Meilisearch')
    parser.add_argument('--csv', default='enriched_final.csv', help='Path to CSV file')
    parser.add_argument('--host', default='http://localhost:7700', help='Meilisearch host')
    parser.add_argument('--key', default='masterKey', help='Meilisearch API key')
    parser.add_argument('--index', default='repositories', help='Index name')
    parser.add_argument('--batch', type=int, default=1000, help='Batch size')
    
    args = parser.parse_args()
    
    index_repositories(
        csv_path=args.csv,
        host=args.host,
        api_key=args.key,
        index_name=args.index,
        batch_size=args.batch
    )
