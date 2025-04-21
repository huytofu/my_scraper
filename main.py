#!/usr/bin/env python3
import argparse
import sys
import asyncio
from loguru import logger
from pathlib import Path

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)
logger.add(
    "logs/sports_scraper_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG"
)

from my_scraper.scheduler.jobs import run_scheduler, run_all_now
from my_scraper.scraper.news_scraper import scrape_news
from my_scraper.processing.processor import process_articles, cluster_articles
from my_scraper.processing.highlighter import select_highlights
from my_scraper.database.mongodb import MongoDB


def run_single_job(job_name):
    """Run a single job by name."""
    db = MongoDB()
    
    try:
        # Define coroutine function based on job name
        if job_name == "scrape":
            coro_func = lambda: scrape_news(db)
            job_desc = "Scraping news sources"
        elif job_name == "process":
            coro_func = lambda: process_articles(db)
            job_desc = "Processing raw articles"
        elif job_name == "cluster":
            coro_func = lambda: cluster_articles(db)
            job_desc = "Clustering processed articles"
        elif job_name == "highlight":
            coro_func = lambda: select_highlights(db)
            job_desc = "Selecting highlights"
        else:
            logger.error(f"Unknown job: {job_name}")
            db.close()
            return 1
        
        # Run the job
        logger.info(f"Running job: {job_desc}")
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(coro_func())
        logger.success(f"Job completed: {job_desc}. Result: {result}")
        
    except Exception as e:
        logger.error(f"Error running job {job_name}: {e}")
        return 1
    finally:
        db.close()
    
    return 0


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Sports Event Scraper and Highlighter")
    
    # Define command line arguments
    parser.add_argument("--run-now", action="store_true", help="Run all jobs immediately")
    parser.add_argument("--scheduler", action="store_true", help="Run the scheduler indefinitely")
    parser.add_argument("--job", type=str, choices=["scrape", "process", "cluster", "highlight"], 
                        help="Run a specific job once")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run appropriate function based on arguments
    if args.run_now:
        logger.info("Running all jobs immediately")
        run_all_now()
        return 0
    elif args.scheduler:
        logger.info("Starting scheduler")
        run_scheduler()
        return 0
    elif args.job:
        return run_single_job(args.job)
    else:
        # No valid arguments provided, show help
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 