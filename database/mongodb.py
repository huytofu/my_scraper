from pymongo import MongoClient
from datetime import datetime
from loguru import logger
import time
from my_scraper.config.settings import (
    MONGO_URI, 
    MONGO_DB, 
    MONGO_RAW_ARTICLES_COLLECTION,
    MONGO_PROCESSED_ARTICLES_COLLECTION,
    MONGO_EVENTS_COLLECTION,
    MONGO_HIGHLIGHTS_COLLECTION
)

class MongoDB:
    """MongoDB database handler for sports event scraper (optimized for serverless)."""
    
    # Class-level variables for connection pooling
    _client = None
    _is_connected = False
    _last_used = None
    
    def __init__(self):
        # Use existing connection if recent, otherwise create new
        if MongoDB._client is None or not MongoDB._is_connected or self._connection_expired():
            self._connect()
        else:
            logger.debug("Reusing existing MongoDB connection")
        
        # Set up database and collections
        self.db = MongoDB._client[MONGO_DB]
        self.raw_articles = self.db[MONGO_RAW_ARTICLES_COLLECTION]
        self.processed_articles = self.db[MONGO_PROCESSED_ARTICLES_COLLECTION]
        self.events = self.db[MONGO_EVENTS_COLLECTION]
        self.highlights = self.db[MONGO_HIGHLIGHTS_COLLECTION]
        
        # Update last used timestamp
        MongoDB._last_used = datetime.now()
    
    def _connect(self):
        """Connect to MongoDB with retry logic."""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to MongoDB (attempt {attempt+1}/{max_retries})")
                MongoDB._client = MongoClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=5000,  # 5 second timeout
                    connect=True,                   # Connect immediately
                    maxPoolSize=1,                  # Limit pool size for serverless
                    maxIdleTimeMS=60000            # Close idle connections after 60 seconds
                )
                
                # Test connection
                MongoDB._client.admin.command('ping')
                MongoDB._is_connected = True
                MongoDB._last_used = datetime.now()
                
                # Create indexes if needed
                self._create_indexes()
                logger.info("Successfully connected to MongoDB")
                break
            except Exception as e:
                logger.error(f"MongoDB connection error (attempt {attempt+1}): {e}")
                MongoDB._is_connected = False
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Failed to connect to MongoDB after multiple attempts")
                    raise
    
    def _connection_expired(self):
        """Check if the connection hasn't been used recently and might be stale."""
        if MongoDB._last_used is None:
            return True
        
        # Consider connection expired if not used in the last 5 minutes
        return (datetime.now() - MongoDB._last_used).total_seconds() > 300
    
    def _create_indexes(self):
        """Create necessary indexes for performance optimization."""
        try:
            # Raw articles indexes
            self.raw_articles.create_index([("url", 1)], unique=True)
            self.raw_articles.create_index([("processed", 1)])
            self.raw_articles.create_index([("source", 1)])
            self.raw_articles.create_index([("publication_date", -1)])
            
            # Processed articles indexes
            self.processed_articles.create_index([("raw_id", 1)], unique=True)
            self.processed_articles.create_index([("clustered", 1)])
            self.processed_articles.create_index([("sports_type", 1)])
            self.processed_articles.create_index([("publication_date", -1)])
            
            # Events indexes
            self.events.create_index([("event_id", 1)], unique=True)
            
            # Highlights indexes
            self.highlights.create_index([("event_id", 1)], unique=True)
            
            logger.info("MongoDB indexes created or verified")
        except Exception as e:
            logger.warning(f"Could not create all indexes: {e}")
    
    def save_raw_article(self, article_data):
        """Save raw article to database."""
        article_data["created_at"] = datetime.now()
        article_data["processed"] = False
        
        try:
            result = self.raw_articles.update_one(
                {"url": article_data["url"]},
                {"$set": article_data},
                upsert=True
            )
            return result.upserted_id or True
        except Exception as e:
            logger.error(f"Error saving raw article: {e}")
            return None
    
    def get_unprocessed_articles(self, limit=100):
        """Get unprocessed raw articles."""
        return list(self.raw_articles.find(
            {"processed": False}
        ).limit(limit))
    
    def save_processed_article(self, processed_data):
        """Save processed article to database."""
        processed_data["created_at"] = datetime.now()
        processed_data["clustered"] = False
        
        try:
            result = self.processed_articles.update_one(
                {"raw_id": processed_data["raw_id"]},
                {"$set": processed_data},
                upsert=True
            )
            
            # Mark raw article as processed
            self.raw_articles.update_one(
                {"_id": processed_data["raw_id"]},
                {"$set": {"processed": True}}
            )
            
            return result.upserted_id or True
        except Exception as e:
            logger.error(f"Error saving processed article: {e}")
            return None
    
    def get_unclustered_articles(self):
        """Get all unclustered processed articles."""
        return list(self.processed_articles.find({"clustered": False}))
    
    def update_article_cluster(self, article_id, event_id):
        """Update article with cluster/event information."""
        try:
            self.processed_articles.update_one(
                {"_id": article_id},
                {"$set": {
                    "event_id": event_id, 
                    "clustered": True,
                    "updated_at": datetime.now()
                }}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating article cluster: {e}")
            return False
    
    def save_event(self, event_data):
        """Save event information."""
        event_data["created_at"] = datetime.now()
        
        try:
            result = self.events.update_one(
                {"event_id": event_data["event_id"]},
                {"$set": event_data},
                upsert=True
            )
            return result.upserted_id or True
        except Exception as e:
            logger.error(f"Error saving event: {e}")
            return None
    
    def get_potential_highlight_events(self):
        """Get events that can be considered for highlighting."""
        # Aggregate to find events not yet highlighted with source count
        pipeline = [
            {"$match": {"clustered": True}},
            {"$group": {
                "_id": "$event_id",
                "sources": {"$addToSet": "$source"},
                "latest_date": {"$max": "$publication_date"},
                "sports_type": {"$first": "$sports_type"},
                "title": {"$first": "$title"},
                "entities": {"$first": "$entities"}
            }},
            {"$match": {"_id": {"$nin": self.highlights.distinct("event_id")}}}
        ]
        return list(self.processed_articles.aggregate(pipeline))
    
    def save_highlight(self, highlight_data):
        """Save highlighted event."""
        highlight_data["created_at"] = datetime.now()
        highlight_data["selected"] = True
        
        try:
            result = self.highlights.update_one(
                {"event_id": highlight_data["event_id"]},
                {"$set": highlight_data},
                upsert=True
            )
            return result.upserted_id or True
        except Exception as e:
            logger.error(f"Error saving highlight: {e}")
            return None
    
    def get_highlights(self, limit=10):
        """Get recent highlights ordered by selection date."""
        return list(self.highlights.find().sort("created_at", -1).limit(limit))
    
    def get_articles_by_event(self, event_id):
        """Get all articles related to a specific event."""
        return list(self.processed_articles.find({"event_id": event_id}))
    
    def close(self):
        """Mark connection as no longer in use."""
        # In serverless, we don't actually close connections
        # but keep track of last use time
        MongoDB._last_used = datetime.now()
        logger.debug("MongoDB connection marked as idle") 