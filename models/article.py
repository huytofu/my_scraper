import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime


class RawArticle:
    """Raw news article from the web scraper."""
    
    def __init__(
        self, 
        title: str, 
        content: str, 
        url: str, 
        source: str, 
        publication_date: Optional[datetime] = None
    ):
        self.title = title
        self.content = content
        self.url = url
        self.source = source
        self.publication_date = publication_date or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary for database storage."""
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "source": self.source,
            "publication_date": self.publication_date,
            "processed": False,
            "created_at": datetime.now()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RawArticle':
        """Create instance from dictionary."""
        return cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            url=data.get("url", ""),
            source=data.get("source", ""),
            publication_date=data.get("publication_date")
        )


class ProcessedArticle:
    """Processed news article with extracted features."""
    
    def __init__(
        self, 
        raw_id: str, 
        title: str, 
        content: str, 
        url: str, 
        source: str, 
        sports_type: str, 
        entities: List[str], 
        embedding: List[float], 
        publication_date: Optional[datetime] = None,
        clustered: bool = False
    ):
        self.raw_id = raw_id
        self.title = title
        self.content = content
        self.url = url
        self.source = source
        self.sports_type = sports_type
        self.entities = entities
        self.embedding = embedding
        self.publication_date = publication_date or datetime.now()
        self.clustered = clustered
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary for database storage."""
        return {
            "raw_id": self.raw_id,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "source": self.source,
            "sports_type": self.sports_type,
            "entities": self.entities,
            "embedding": self.embedding,
            "publication_date": self.publication_date,
            "clustered": self.clustered,
            "created_at": datetime.now()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessedArticle':
        """Create instance from dictionary."""
        return cls(
            raw_id=data.get("raw_id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            url=data.get("url", ""),
            source=data.get("source", ""),
            sports_type=data.get("sports_type", "general"),
            entities=data.get("entities", []),
            embedding=data.get("embedding", []),
            publication_date=data.get("publication_date"),
            clustered=data.get("clustered", False)
        )


class Event:
    """Sports event with related articles."""
    
    def __init__(
        self, 
        title: str, 
        sports_type: str, 
        entities: List[str], 
        sources: List[str], 
        latest_date: Optional[datetime] = None,
        event_id: Optional[str] = None
    ):
        self.event_id = event_id or str(uuid.uuid4())
        self.title = title
        self.sports_type = sports_type
        self.entities = entities
        self.sources = sources
        self.latest_date = latest_date or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary for database storage."""
        return {
            "event_id": self.event_id,
            "title": self.title,
            "sports_type": self.sports_type,
            "entities": self.entities,
            "sources": self.sources,
            "latest_date": self.latest_date,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create instance from dictionary."""
        return cls(
            event_id=data.get("event_id"),
            title=data.get("title", ""),
            sports_type=data.get("sports_type", "general"),
            entities=data.get("entities", []),
            sources=data.get("sources", []),
            latest_date=data.get("latest_date")
        )


class Highlight:
    """Highlight or key moment from an event."""
    
    def __init__(
        self, 
        event_id: str, 
        title: str, 
        description: str, 
        source: str, 
        timestamp: Optional[datetime] = None,
        highlight_id: Optional[str] = None
    ):
        self.highlight_id = highlight_id or str(uuid.uuid4())
        self.event_id = event_id
        self.title = title
        self.description = description
        self.source = source
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary for database storage."""
        return {
            "highlight_id": self.highlight_id,
            "event_id": self.event_id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "timestamp": self.timestamp,
            "created_at": datetime.now()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Highlight':
        """Create instance from dictionary."""
        return cls(
            highlight_id=data.get("highlight_id"),
            event_id=data.get("event_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            source=data.get("source", ""),
            timestamp=data.get("timestamp")
        ) 