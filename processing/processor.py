import re
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from loguru import logger
import numpy as np
import requests
import json
import os
from sklearn.cluster import DBSCAN
import time
import hashlib

from my_scraper.models.article import RawArticle, ProcessedArticle, Event
from my_scraper.database.mongodb import MongoDB
from my_scraper.config.settings import (
    CLUSTERING_DISTANCE_THRESHOLD,
    EMBEDDING_MODEL,
    SPORTS_CATEGORIES
)

# HuggingFace API settings
HF_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
HF_API_EMBEDDING_URL = f"https://api-inference.huggingface.co/models/{EMBEDDING_MODEL}"
HF_API_NER_URL = "https://api-inference.huggingface.co/models/dslim/bert-base-NER"

# API Headers
headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}

# Caching for API responses to reduce costs and improve performance in serverless environments
api_cache = {}
CACHE_MAX_SIZE = int(os.getenv("API_CACHE_MAX_SIZE", "500"))

def query_huggingface_api(payload, api_url):
    """Query the HuggingFace Inference API with caching."""
    # Create a cache key based on the payload and URL
    payload_str = json.dumps(payload, sort_keys=True)
    cache_key = hashlib.md5(f"{api_url}:{payload_str}".encode()).hexdigest()
    
    # Check if response is in cache
    if cache_key in api_cache:
        logger.debug(f"Using cached API response for {api_url}")
        return api_cache[cache_key]
    
    # Make API request with retries
    max_retries = 3
    backoff_factor = 1.5
    
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                # Cache the result
                api_cache[cache_key] = result
                # Clean cache if too large
                if len(api_cache) > CACHE_MAX_SIZE:
                    # Remove oldest 20% of cache entries
                    keys_to_remove = list(api_cache.keys())[:int(CACHE_MAX_SIZE * 0.2)]
                    for key in keys_to_remove:
                        api_cache.pop(key, None)
                return result
            elif response.status_code == 429:  # Rate limit
                logger.warning(f"Rate limited by HuggingFace API (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    sleep_time = backoff_factor ** attempt
                    time.sleep(sleep_time)
                    continue
            else:
                logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error querying HuggingFace API (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                sleep_time = backoff_factor ** attempt
                time.sleep(sleep_time)
                continue
    
    # If we got here, all retries failed
    return None

def get_embeddings(texts):
    """Get embeddings from HuggingFace Inference API with optimized batching."""
    if not texts:
        return []
        
    # Standardize input to list format
    single_input = False
    if isinstance(texts, str):
        texts = [texts]
        single_input = True
    
    # Handle batching for better performance
    batch_size = 8  # Adjust based on model size and API limits
    if len(texts) > batch_size:
        # Process in batches
        all_results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            logger.debug(f"Processing embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            payload = {"inputs": batch, "options": {"wait_for_model": True}}
            batch_results = query_huggingface_api(payload, HF_API_EMBEDDING_URL)
            if batch_results:
                # Handle different response formats
                if isinstance(batch_results, list):
                    all_results.extend(batch_results)
                elif isinstance(batch_results, dict):
                    # If we got a single result for multiple inputs, replicate it
                    all_results.extend([batch_results] * len(batch))
            else:
                # Fill with empty results for failed batch
                all_results.extend([[] for _ in range(len(batch))])
        result = all_results
    else:
        # Process as a single request
        payload = {"inputs": texts, "options": {"wait_for_model": True}}
        result = query_huggingface_api(payload, HF_API_EMBEDDING_URL)
        # If not a list, convert to list format for consistency
        if result and not isinstance(result, list):
            result = [result] * len(texts)
    
    # Return single result if input was single string
    if single_input and result:
        return result[0]
    return result

def get_entities(texts):
    """Get named entities from HuggingFace Inference API with batch support."""
    if not texts:
        return []
        
    # Standardize input to list format
    single_input = False
    if isinstance(texts, str):
        texts = [texts]
        single_input = True
    
    # Handle batching
    batch_size = 4  # NER models typically handle smaller batches
    if len(texts) > batch_size:
        # Process in batches
        all_results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            logger.debug(f"Processing NER batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            payload = {"inputs": batch, "options": {"wait_for_model": True, "use_cache": True}}
            batch_results = query_huggingface_api(payload, HF_API_NER_URL)
            if batch_results:
                # Handle different response formats
                if isinstance(batch_results, list):
                    all_results.extend(batch_results)
                elif isinstance(batch_results, dict):
                    # If we got a single result, replicate it
                    all_results.extend([batch_results] * len(batch))
            else:
                # Fill with empty results for failed batch
                all_results.extend([[] for _ in range(len(batch))])
        result = all_results
    else:
        # Process as a single request
        payload = {"inputs": texts, "options": {"wait_for_model": True, "use_cache": True}}
        result = query_huggingface_api(payload, HF_API_NER_URL)
        # If not a list, convert to list format for consistency
        if result and not isinstance(result, list) and len(texts) > 1:
            result = [result] * len(texts)
    
    # Return single result if input was single string
    if single_input and result:
        return result[0]
    return result

def extract_entities_from_ner_result(ner_result) -> List[str]:
    """Extract entity strings from NER API result in various formats."""
    if not ner_result:
        return []
        
    entities = []
    
    # Handle potential response formats
    if isinstance(ner_result, list) and all(isinstance(e, dict) for e in ner_result):
        # Standard format with entity objects
        for entity in ner_result:
            if entity.get('score', 0) > 0.75 and 'word' in entity:
                entities.append(entity['word'])
    elif isinstance(ner_result, dict):
        if 'entities' in ner_result:
            # Alternative format with nested entities
            for entity in ner_result['entities']:
                if entity.get('score', 0) > 0.75 and 'word' in entity:
                    entities.append(entity['word'])
        elif 'entity' in ner_result and 'score' in ner_result:
            # Simple single entity format
            if ner_result.get('score', 0) > 0.75:
                entities.append(ner_result['entity'])
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(entities))

class ArticleProcessor:
    """Processor for extracting features from raw articles."""
    
    def __init__(self, db: MongoDB):
        self.db = db
    
    async def process_articles(self, limit: int = 100) -> int:
        """Process unprocessed articles from database with optimized batch processing."""
        # Get unprocessed articles
        raw_articles = self.db.get_unprocessed_articles(limit)
        logger.info(f"Processing {len(raw_articles)} raw articles")
        
        if not raw_articles:
            logger.info("No articles to process")
            return 0
        
        # Prepare batch processing data
        article_data = []
        
        # First batch process: Extract sports types (no API call needed)
        for raw_article_dict in raw_articles:
            try:
                # Convert dict to RawArticle object
                raw_article = RawArticle.from_dict(raw_article_dict)
                
                # Extract sports type first (doesn't require API call)
                sports_type = self._extract_sports_type(raw_article.title, raw_article.content)
                
                # Prepare data for next stages
                article_data.append({
                    "raw_id": str(raw_article_dict["_id"]),
                    "raw_article": raw_article,
                    "sports_type": sports_type,
                    "entities": [],
                    "embedding": []
                })
            except Exception as e:
                logger.error(f"Error preparing article {raw_article_dict.get('_id')}: {e}")
        
        # Second batch process: Extract entities
        ner_texts = [f"{data['raw_article'].title}. {data['raw_article'].content[:1000]}" for data in article_data]
        ner_results = get_entities(ner_texts)
        
        # Process NER results
        for i, data in enumerate(article_data):
            if i < len(ner_results) and ner_results[i]:
                data["entities"] = extract_entities_from_ner_result(ner_results[i])
        
        # Third batch process: Generate embeddings
        embedding_texts = []
        for data in article_data:
            # Combine title, entities, and start of content for embedding
            entities_text = " ".join(data["entities"]) if data["entities"] else ""
            text_for_embedding = f"{data['raw_article'].title} {entities_text} {data['raw_article'].content[:1500]}"
            embedding_texts.append(text_for_embedding)
        
        embedding_results = get_embeddings(embedding_texts)
        
        # Process results and save to database
        processed_count = 0
        for i, data in enumerate(article_data):
            try:
                # Extract embedding from result
                embedding = []
                if i < len(embedding_results) and embedding_results[i]:
                    result = embedding_results[i]
                    if isinstance(result, list):
                        embedding = result
                    elif isinstance(result, dict) and 'embedding' in result:
                        embedding = result['embedding']
                    # Ensure embedding is a list of floats
                    if embedding and not all(isinstance(x, (int, float)) for x in embedding):
                        logger.warning(f"Invalid embedding format for article {data['raw_id']}")
                        embedding = []
                
                # Create processed article
                processed_article = ProcessedArticle(
                    raw_id=data["raw_id"],
                    title=data["raw_article"].title,
                    content=data["raw_article"].content,
                    url=data["raw_article"].url,
                    source=data["raw_article"].source,
                    sports_type=data["sports_type"],
                    entities=data["entities"],
                    embedding=embedding,
                    publication_date=data["raw_article"].publication_date
                )
                
                # Save to database
                self.db.save_processed_article(processed_article.to_dict())
                
                # Mark raw article as processed
                self.db.update_raw_article_processed(data["raw_id"])
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error finalizing processing for article {data['raw_id']}: {e}")
        
        logger.success(f"Processed {processed_count} articles")
        return processed_count
    
    def _extract_sports_type(self, title: str, content: str) -> str:
        """Extract the sports type from article title and content."""
        # Combine title and content for better detection
        text = f"{title} {content}".lower()
        
        # Check for each sport category
        matches = {}
        for sport in SPORTS_CATEGORIES:
            # Count occurrences of the sport name
            count = len(re.findall(r'\b' + re.escape(sport) + r'\b', text))
            if count > 0:
                matches[sport] = count
        
        # Return the sport with the highest count, or "general" if none found
        if matches:
            return max(matches.items(), key=lambda x: x[1])[0]
        else:
            return "general"

class EventClusterer:
    """Clusterer for grouping articles into sports events."""
    
    def __init__(self, db: MongoDB):
        self.db = db
    
    async def cluster_articles(self) -> int:
        """Cluster unclustered articles into events."""
        # Get unclustered articles
        unclustered_articles = self.db.get_unclustered_articles()
        logger.info(f"Clustering {len(unclustered_articles)} articles")
        
        if not unclustered_articles:
            logger.info("No articles to cluster")
            return 0
        
        # Group by sports type for more efficient clustering
        by_sport = self._group_by_sports_type(unclustered_articles)
        
        total_clustered = 0
        for sport, articles in by_sport.items():
            # Skip if less than 2 articles (can't cluster)
            if len(articles) < 2:
                logger.info(f"Not enough articles for sport {sport} to cluster")
                # Mark single articles as their own cluster
                if len(articles) == 1:
                    article = articles[0]
                    event = Event(
                        title=article.get("title", ""),
                        sports_type=sport,
                        entities=article.get("entities", []),
                        sources=[article.get("source", "")],
                        latest_date=article.get("publication_date", datetime.now())
                    )
                    self.db.save_event(event.to_dict())
                    self.db.update_article_cluster(article["_id"], event.event_id)
                    total_clustered += 1
                continue
            
            # Get embeddings
            embeddings = [article.get("embedding", []) for article in articles]
            
            # Skip articles with empty embeddings
            valid_indices = [i for i, emb in enumerate(embeddings) if emb]
            if len(valid_indices) < 2:
                logger.info(f"Not enough articles with valid embeddings for sport {sport}")
                continue
            
            valid_embeddings = [embeddings[i] for i in valid_indices]
            valid_articles = [articles[i] for i in valid_indices]
            
            # Use DBSCAN for clustering - most efficient for serverless
            clusters = self._dbscan_clustering(valid_embeddings)
            
            # Process each cluster
            clustered_in_sport = 0
            for cluster_id, indices in enumerate(clusters):
                # Skip if empty cluster
                if not indices:
                    continue
                
                # Get cluster articles
                cluster_articles = [valid_articles[i] for i in indices]
                
                # Create a new event
                event_id = self._create_or_match_event(cluster_articles, sport)
                
                # Update articles with cluster/event info
                for article in cluster_articles:
                    self.db.update_article_cluster(article["_id"], event_id)
                    clustered_in_sport += 1
            
            logger.info(f"Clustered {clustered_in_sport} articles for sport {sport}")
            total_clustered += clustered_in_sport
        
        logger.success(f"Total articles clustered: {total_clustered}")
        return total_clustered
    
    def _group_by_sports_type(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Group articles by sports type."""
        by_sport = {}
        for article in articles:
            sport = article.get("sports_type", "general")
            if sport not in by_sport:
                by_sport[sport] = []
            by_sport[sport].append(article)
        return by_sport
    
    def _dbscan_clustering(self, embeddings: List[List[float]]) -> List[List[int]]:
        """Use DBSCAN for efficient clustering in serverless environments."""
        try:
            if not embeddings:
                return []
                
            # Convert to numpy array
            X = np.array(embeddings)
            
            # Normalize embeddings for cosine distance
            norms = np.linalg.norm(X, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Avoid division by zero
            X_normalized = X / norms
            
            # Use DBSCAN with cosine metric
            # eps is equivalent to 1-CLUSTERING_DISTANCE_THRESHOLD for cosine
            eps = 1 - CLUSTERING_DISTANCE_THRESHOLD
            db = DBSCAN(eps=eps, min_samples=1, metric='cosine', n_jobs=-1).fit(X_normalized)
            
            # Group indices by cluster label
            labels = db.labels_
            clusters = {}
            for i, label in enumerate(labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(i)
            
            return list(clusters.values())
            
        except Exception as e:
            logger.error(f"DBSCAN clustering error: {e}")
            # Fallback to simple similarity matching
            return self._fallback_clustering(embeddings)
    
    def _fallback_clustering(self, embeddings: List[List[float]]) -> List[List[int]]:
        """Fallback clustering method that uses similarity thresholds directly."""
        clusters = []
        used_indices = set()
        
        for i in range(len(embeddings)):
            if i in used_indices:
                continue
                
            cluster = [i]
            used_indices.add(i)
            
            # Find similar embeddings
            for j in range(i+1, len(embeddings)):
                if j in used_indices:
                    continue
                    
                # Calculate cosine similarity manually to avoid full matrix calculation
                vec1 = np.array(embeddings[i])
                vec2 = np.array(embeddings[j])
                
                # Normalize vectors
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                
                if norm1 == 0 or norm2 == 0:
                    continue  # Skip zero vectors
                
                similarity = np.dot(vec1, vec2) / (norm1 * norm2)
                
                # If similarity is above threshold (1 - distance_threshold)
                if similarity > (1 - CLUSTERING_DISTANCE_THRESHOLD):
                    cluster.append(j)
                    used_indices.add(j)
            
            clusters.append(cluster)
            
            # Process at most 100 clusters to ensure we don't timeout
            if len(clusters) >= 100:
                # Add remaining articles as single-item clusters
                for k in range(len(embeddings)):
                    if k not in used_indices:
                        clusters.append([k])
                        used_indices.add(k)
                break
        
        return clusters
    
    def _create_or_match_event(self, cluster_articles: List[Dict], sport: str) -> str:
        """Create a new event or match to an existing one."""
        # Get titles, entities, and sources
        titles = [article.get("title", "") for article in cluster_articles]
        entities_lists = [article.get("entities", []) for article in cluster_articles]
        sources = list(set(article.get("source", "") for article in cluster_articles))
        
        # Flatten and deduplicate entities
        all_entities = []
        for entities in entities_lists:
            all_entities.extend(entities)
        unique_entities = list(dict.fromkeys(all_entities))
        
        # Get the latest publication date
        pub_dates = [article.get("publication_date", datetime.now()) for article in cluster_articles]
        latest_date = max(pub_dates)
        
        # Use the title of the most recent article as the event title
        most_recent_idx = pub_dates.index(latest_date)
        event_title = titles[most_recent_idx]
        
        # Create a new event
        event = Event(
            title=event_title,
            sports_type=sport,
            entities=unique_entities,
            sources=sources,
            latest_date=latest_date
        )
        
        # Save to database
        self.db.save_event(event.to_dict())
        
        return event.event_id


async def process_articles(db: MongoDB = None) -> int:
    """Process raw articles from database."""
    try:
        # Create a new database connection if not provided
        should_close_db = False
        if db is None:
            db = MongoDB()
            should_close_db = True
        
        # Process articles
        processor = ArticleProcessor(db)
        processed_count = await processor.process_articles()
        
        # Close the database connection if we created it
        if should_close_db:
            db.close()
            
        return processed_count
        
    except Exception as e:
        logger.error(f"Error in process_articles: {e}")
        return 0

async def cluster_articles(db: MongoDB = None) -> int:
    """Cluster processed articles into events."""
    try:
        # Create a new database connection if not provided
        should_close_db = False
        if db is None:
            db = MongoDB()
            should_close_db = True
        
        # Cluster articles
        clusterer = EventClusterer(db)
        clustered_count = await clusterer.cluster_articles()
        
        # Close the database connection if we created it
        if should_close_db:
            db.close()
            
        return clustered_count
        
    except Exception as e:
        logger.error(f"Error in cluster_articles: {e}")
        return 0 