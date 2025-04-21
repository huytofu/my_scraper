from fastapi import FastAPI, Depends, BackgroundTasks
from datetime import datetime
from loguru import logger
from typing import Optional, List, Dict, Any

# Import our modules
from my_scraper.scraper.news_scraper import scrape_news
from my_scraper.processing.processor import process_articles, cluster_articles
from my_scraper.processing.highlighter import select_highlights
from my_scraper.database.mongodb import MongoDB

# Initialize FastAPI
app = FastAPI(title="Sports Event Scraper API")

# Configure logger for serverless environment (no file output)
logger.remove()
logger.add(lambda msg: print(msg), level="INFO")

# MongoDB connection singleton
db_instance = None

def get_db():
    """Get MongoDB connection, reusing existing connection if available."""
    global db_instance
    if db_instance is None:
        db_instance = MongoDB()
    return db_instance

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Sports Event Scraper API", "timestamp": datetime.now().isoformat()}

@app.post("/api/scrape")
async def api_scrape(background_tasks: BackgroundTasks):
    """Trigger the scraping process."""
    db = get_db()
    
    # Run in background to avoid timeouts
    background_tasks.add_task(scrape_news, db)
    
    return {
        "status": "started",
        "message": "Scraping process initiated in background",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/process")
async def api_process(background_tasks: BackgroundTasks):
    """Process raw articles."""
    db = get_db()
    
    # Run in background
    background_tasks.add_task(process_articles, db)
    
    return {
        "status": "started",
        "message": "Processing initiated in background",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/cluster")
async def api_cluster(background_tasks: BackgroundTasks):
    """Cluster processed articles."""
    db = get_db()
    
    # Run in background
    background_tasks.add_task(cluster_articles, db)
    
    return {
        "status": "started",
        "message": "Clustering initiated in background",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/highlight")
async def api_highlight(background_tasks: BackgroundTasks):
    """Select highlights from clustered articles."""
    db = get_db()
    
    # Run in background
    background_tasks.add_task(select_highlights, db)
    
    return {
        "status": "started",
        "message": "Highlight selection initiated in background",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/run-all")
async def api_run_all(background_tasks: BackgroundTasks):
    """Run the entire pipeline sequentially."""
    db = get_db()
    
    async def run_pipeline():
        """Run all steps sequentially."""
        try:
            logger.info("Starting complete pipeline")
            
            # Step 1: Scrape
            scrape_result = await scrape_news(db)
            logger.info(f"Scraping completed: {scrape_result} articles scraped")
            
            # Step 2: Process
            process_result = await process_articles(db)
            logger.info(f"Processing completed: {process_result} articles processed")
            
            # Step 3: Cluster
            cluster_result = await cluster_articles(db)
            logger.info(f"Clustering completed: {cluster_result} articles clustered")
            
            # Step 4: Highlight
            highlight_result = await select_highlights(db)
            logger.info(f"Highlighting completed: {highlight_result} highlights selected")
            
            logger.info("Pipeline completed successfully")
        except Exception as e:
            logger.error(f"Error in pipeline: {e}")
    
    # Run in background
    background_tasks.add_task(run_pipeline)
    
    return {
        "status": "started",
        "message": "Full pipeline initiated in background",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/highlights")
async def get_highlights(limit: int = 10, db: MongoDB = Depends(get_db)):
    """Get recent highlights."""
    highlights = db.get_highlights(limit)
    
    # Convert ObjectId to string for JSON serialization
    serializable_highlights = []
    for highlight in highlights:
        highlight['_id'] = str(highlight.get('_id', ''))
        if 'created_at' in highlight:
            highlight['created_at'] = highlight['created_at'].isoformat()
        if 'latest_date' in highlight:
            highlight['latest_date'] = highlight['latest_date'].isoformat()
        serializable_highlights.append(highlight)
    
    return {"highlights": serializable_highlights}

@app.get("/api/articles/{event_id}")
async def get_event_articles(event_id: str, db: MongoDB = Depends(get_db)):
    """Get articles for a specific event."""
    articles = db.get_articles_by_event(event_id)
    
    # Convert ObjectId to string for JSON serialization
    serializable_articles = []
    for article in articles:
        article['_id'] = str(article.get('_id', ''))
        if 'created_at' in article:
            article['created_at'] = article['created_at'].isoformat()
        if 'publication_date' in article:
            article['publication_date'] = article['publication_date'].isoformat()
        serializable_articles.append(article)
    
    return {"event_id": event_id, "articles": serializable_articles} 