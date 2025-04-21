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
MONGO_RAW_ARTICLES_COLLECTION = "raw_articles"
MONGO_PROCESSED_ARTICLES_COLLECTION = "processed_articles"
MONGO_EVENTS_COLLECTION = "events"
MONGO_HIGHLIGHTS_COLLECTION = "highlights"

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

# Sports type importance (higher = more important)
SPORTS_IMPORTANCE = {
    "football": 1.2,
    "soccer": 1.2,
    "basketball": 1.1,
    "tennis": 1.0,
    "baseball": 1.0,
    "hockey": 0.9,
    "golf": 0.9,
    "cricket": 0.8,
    "rugby": 0.8,
    "formula 1": 1.1
}

# News sources to scrape
NEWS_SOURCES = [
    {
        "name": "BETMGM",
        "url": "https://sports.betmgm.com/en/blog",
        "article_selector": "single-news",
        "title_selector": "h1",
        "content_selector": "article-content-container",
        "date_selector": "title-date"
    },
    {
        "name": "Transfermarkt",
        "url": "https://www.transfermarkt.com/betting/tips",
        "article_selector": "status-publish",
        "title_selector": "page__header",
        "content_selector": "page__content",
        "date_selector": "page__date"
    },
    {
        "name": "Sky Sports",
        "url": "https://www.skysports.com/",
        "article_selector": ".news-list__item",
        "title_selector": ".news-list__headline-link",
        "content_selector": ".sdc-article-body",
        "date_selector": ".sdc-article-date"
    },
    {
        "name": "CBS Sports",
        "url": "https://www.cbssports.com/",
        "article_selector": ".article-list-marquee-item",
        "title_selector": ".article-list-marquee-item-headline",
        "content_selector": ".Article-bodyContent",
        "date_selector": ".Article-datePublished"
    }
]

# Clustering parameters
CLUSTERING_DISTANCE_THRESHOLD = 0.2
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"  # Advanced embedding model

# Highlight selection parameters
TOP_N_HIGHLIGHTS = 5
FRESHNESS_WEIGHT = 0.5  # Weight for freshness score (days)
COVERAGE_WEIGHT = 1.0   # Weight for source coverage

# Scheduler settings
SCRAPE_INTERVAL_HOURS = 3
PROCESS_INTERVAL_HOURS = 3  # Run processing right after scraping
CLUSTER_HIGHLIGHT_TIMES = ["00:00", "12:00"]  # Midnight and noon