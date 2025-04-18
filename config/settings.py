import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# SerpAPI settings
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
MAX_REQUESTS_PER_HOUR = int(os.getenv("MAX_REQUESTS_PER_HOUR", "60"))
SEARCH_DELAY = int(os.getenv("SEARCH_DELAY", "5"))  # seconds between requests

# MongoDB settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "sports_events")
MONGO_EVENTS_COLLECTION = "events"
MONGO_SOURCES_COLLECTION = "sources"

# Search parameters
SPORTS_CATEGORIES = [
    "football", "basketball", "soccer", "tennis", "baseball", 
    "hockey", "golf", "cricket", "rugby", "formula 1"
]

# Query templates
QUERY_TEMPLATES = [
    "{sport} upcoming events",
    "{sport} tournament schedule",
    "{sport} match today",
    "trending {sport} events",
    "{sport} championship"
]