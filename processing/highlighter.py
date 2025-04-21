from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger

from my_scraper.database.mongodb import MongoDB
from my_scraper.models.article import Highlight
from my_scraper.config.settings import (
    TOP_N_HIGHLIGHTS,
    SPORTS_IMPORTANCE,
    FRESHNESS_WEIGHT,
    COVERAGE_WEIGHT
)

class EventHighlighter:
    """Highlighter for selecting the most important sports events."""
    
    def __init__(self, db: MongoDB):
        self.db = db
    
    async def select_highlights(self, top_n: int = TOP_N_HIGHLIGHTS) -> int:
        """Select top events for highlighting."""
        # Get potential events for highlighting
        potential_events = self.db.get_potential_highlight_events()
        logger.info(f"Found {len(potential_events)} potential events for highlighting")
        
        if not potential_events:
            logger.info("No events to highlight")
            return 0
        
        # Score events
        scored_events = []
        for event in potential_events:
            score = self._score_event(event)
            scored_events.append((event, score))
        
        # Sort by score (descending)
        scored_events.sort(key=lambda x: x[1], reverse=True)
        
        # Select top N events
        selected_count = 0
        for event, score in scored_events[:top_n]:
            # Create highlight object
            highlight = Highlight(
                event_id=event["_id"],
                title=event.get("title", "Untitled Event"),
                sports_type=event.get("sports_type", "general"),
                sources=event.get("sources", []),
                score=score,
                latest_date=event.get("latest_date", datetime.now())
            )
            
            # Save to database
            self.db.save_highlight(highlight.to_dict())
            selected_count += 1
            
            logger.info(f"Selected event for highlighting: {highlight.title} (score: {score:.2f})")
        
        logger.success(f"Selected {selected_count} events for highlighting")
        return selected_count
    
    def _score_event(self, event: Dict[str, Any]) -> float:
        """Score an event based on configured criteria."""
        # 1. Source coverage score (number of different sources covering the event)
        sources = event.get("sources", [])
        coverage_score = len(sources) * COVERAGE_WEIGHT
        
        # 2. Freshness score (how recent is the event)
        latest_date = event.get("latest_date", datetime.now())
        days_old = (datetime.now() - latest_date).total_seconds() / 86400  # Convert to days
        freshness_score = max(0, 3 - days_old) * FRESHNESS_WEIGHT  # Older events get lower scores
        
        # 3. Sport importance score
        sport = event.get("sports_type", "general")
        importance = SPORTS_IMPORTANCE.get(sport, 1.0)
        
        # Combine scores
        total_score = coverage_score + freshness_score + importance
        
        return total_score


async def select_highlights(db: MongoDB = None) -> int:
    """Select top events for highlighting."""
    try:
        # Create a new database connection if not provided
        should_close_db = False
        if db is None:
            db = MongoDB()
            should_close_db = True
        
        # Select highlights
        highlighter = EventHighlighter(db)
        highlighted_count = await highlighter.select_highlights()
        
        # Close the database connection if we created it
        if should_close_db:
            db.close()
            
        return highlighted_count
        
    except Exception as e:
        logger.error(f"Error in select_highlights: {e}")
        return 0 