import asyncio
import schedule
import time
import signal
import sys
from datetime import datetime
from loguru import logger

from my_scraper.scraper.news_scraper import scrape_news
from my_scraper.processing.processor import process_articles, cluster_articles
from my_scraper.processing.highlighter import select_highlights
from my_scraper.database.mongodb import MongoDB
from my_scraper.config.settings import (
    SCRAPE_INTERVAL_HOURS,
    PROCESS_INTERVAL_HOURS,
    CLUSTER_HIGHLIGHT_TIMES
)

# Global flag for graceful shutdown
running = True

def run_async_job(coroutine_func):
    """Run an async job in the event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(coroutine_func())
    loop.close()
    return result

def schedule_scrape_job():
    """Schedule job for scraping news sources."""
    logger.info("Running scheduled scrape job")
    db = MongoDB()
    try:
        result = run_async_job(lambda: scrape_news(db))
        logger.info(f"Scrape job completed. Scraped {result} articles.")
    except Exception as e:
        logger.error(f"Error in scrape job: {e}")
    finally:
        db.close()

def schedule_process_job():
    """Schedule job for processing raw articles."""
    logger.info("Running scheduled process job")
    db = MongoDB()
    try:
        result = run_async_job(lambda: process_articles(db))
        logger.info(f"Process job completed. Processed {result} articles.")
    except Exception as e:
        logger.error(f"Error in process job: {e}")
    finally:
        db.close()

def schedule_cluster_and_highlight_job():
    """Schedule job for clustering articles and selecting highlights."""
    logger.info("Running scheduled cluster and highlight job")
    db = MongoDB()
    try:
        # Run clustering
        cluster_result = run_async_job(lambda: cluster_articles(db))
        logger.info(f"Cluster job completed. Clustered {cluster_result} articles.")
        
        # Run highlighting
        highlight_result = run_async_job(lambda: select_highlights(db))
        logger.info(f"Highlight job completed. Selected {highlight_result} highlights.")
    except Exception as e:
        logger.error(f"Error in cluster and highlight job: {e}")
    finally:
        db.close()

def setup_scheduler():
    """Set up the scheduler for regular jobs."""
    # Schedule scrape jobs every N hours
    for hour in range(0, 24, SCRAPE_INTERVAL_HOURS):
        schedule.every().day.at(f"{hour:02d}:00").do(schedule_scrape_job)
        logger.info(f"Scheduled scrape job at {hour:02d}:00")
    
    # Schedule process jobs every N hours, 15 minutes after scraping
    for hour in range(0, 24, PROCESS_INTERVAL_HOURS):
        schedule.every().day.at(f"{hour:02d}:15").do(schedule_process_job)
        logger.info(f"Scheduled process job at {hour:02d}:15")
    
    # Schedule cluster and highlight jobs at specified times
    for time_str in CLUSTER_HIGHLIGHT_TIMES:
        schedule.every().day.at(time_str).do(schedule_cluster_and_highlight_job)
        logger.info(f"Scheduled cluster and highlight job at {time_str}")

def signal_handler(sig, frame):
    """Handle termination signals."""
    global running
    logger.info("Received termination signal. Shutting down...")
    running = False

def run_scheduler():
    """Run the scheduler indefinitely."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    setup_scheduler()
    
    logger.info("Scheduler started. Press Ctrl+C to exit.")
    
    # Immediately run a scrape and process job at startup
    schedule_scrape_job()
    schedule_process_job()
    
    # Run the scheduler loop
    while running:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
    
    logger.info("Scheduler stopped.")

def run_all_now():
    """Run all jobs immediately (useful for testing)."""
    logger.info("Running all jobs immediately")
    
    # Create a shared database connection
    db = MongoDB()
    
    try:
        # Run scrape job
        scrape_result = run_async_job(lambda: scrape_news(db))
        logger.info(f"Immediate scrape job completed. Scraped {scrape_result} articles.")
        
        # Run process job
        process_result = run_async_job(lambda: process_articles(db))
        logger.info(f"Immediate process job completed. Processed {process_result} articles.")
        
        # Run cluster job
        cluster_result = run_async_job(lambda: cluster_articles(db))
        logger.info(f"Immediate cluster job completed. Clustered {cluster_result} articles.")
        
        # Run highlight job
        highlight_result = run_async_job(lambda: select_highlights(db))
        logger.info(f"Immediate highlight job completed. Selected {highlight_result} highlights.")
        
    except Exception as e:
        logger.error(f"Error running all jobs: {e}")
    finally:
        db.close()

# Define job functions that handle their own database connections

async def job_scrape():
    """Scrape news sources job."""
    db = MongoDB()
    try:
        logger.info("Starting job: Scraping news sources")
        result = await scrape_news(db)
        logger.success(f"Completed scraping job. Scraped {result} articles")
        return result
    except Exception as e:
        logger.error(f"Error in scraping job: {e}")
        return 0
    finally:
        db.close()

async def job_process():
    """Process raw articles job."""
    db = MongoDB()
    try:
        logger.info("Starting job: Processing raw articles")
        result = await process_articles(db)
        logger.success(f"Completed processing job. Processed {result} articles")
        return result
    except Exception as e:
        logger.error(f"Error in processing job: {e}")
        return 0
    finally:
        db.close()

async def job_cluster():
    """Cluster processed articles job."""
    db = MongoDB()
    try:
        logger.info("Starting job: Clustering processed articles")
        result = await cluster_articles(db)
        logger.success(f"Completed clustering job. Clustered {result} articles")
        return result
    except Exception as e:
        logger.error(f"Error in clustering job: {e}")
        return 0
    finally:
        db.close()

async def job_highlight():
    """Select highlights job."""
    db = MongoDB()
    try:
        logger.info("Starting job: Selecting highlights")
        result = await select_highlights(db)
        logger.success(f"Completed highlighting job. Selected {result} highlights")
        return result
    except Exception as e:
        logger.error(f"Error in highlighting job: {e}")
        return 0
    finally:
        db.close()

async def run_pipeline():
    """Run the full pipeline sequentially."""
    start_time = datetime.now()
    logger.info(f"Starting full pipeline at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run jobs in sequence
    await job_scrape()
    await job_process()
    await job_cluster()
    await job_highlight()
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.success(f"Completed full pipeline in {duration:.2f} seconds")

def run_all_now():
    """Run all jobs immediately in sequence."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_pipeline())
    finally:
        loop.close()

def run_scheduler():
    """Run the scheduler indefinitely, executing jobs at scheduled times."""
    logger.info("Starting scheduler")
    
    # Schedule scraping job
    schedule.every(SCRAPE_INTERVAL_HOURS).hours.do(
        lambda: asyncio.run(job_scrape())
    )
    logger.info(f"Scheduled scraping job to run every {SCRAPE_INTERVAL_HOURS} hours")
    
    # Schedule processing job
    schedule.every(PROCESS_INTERVAL_HOURS).hours.do(
        lambda: asyncio.run(job_process())
    )
    logger.info(f"Scheduled processing job to run every {PROCESS_INTERVAL_HOURS} hours")
    
    # Schedule clustering and highlighting jobs at specific times
    for time_str in CLUSTER_HIGHLIGHT_TIMES:
        # Schedule clustering
        schedule.every().day.at(time_str).do(
            lambda: asyncio.run(job_cluster())
        )
        
        # Schedule highlighting 15 minutes after clustering
        hour, minute = map(int, time_str.split(':'))
        minute = (minute + 15) % 60
        hour = (hour + 1) if minute < 15 else hour
        highlight_time = f"{hour:02d}:{minute:02d}"
        
        schedule.every().day.at(highlight_time).do(
            lambda: asyncio.run(job_highlight())
        )
        
        logger.info(f"Scheduled clustering at {time_str} and highlighting at {highlight_time}")
    
    # Run the scheduler loop
    logger.info("Scheduler started. Running indefinitely...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            # Continue running despite errors
            time.sleep(300)  # Sleep longer after error

if __name__ == "__main__":
    # Configure logger
    logger.add(
        "logs/scheduler_{time}.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--run-now":
        run_all_now()
    else:
        run_scheduler() 