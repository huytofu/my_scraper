import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from loguru import logger
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from my_scraper.config.settings import NEWS_SOURCES
from my_scraper.models.article import RawArticle
from my_scraper.database.mongodb import MongoDB

class NewsScraper:
    """Scraper for extracting articles from news sources."""
    
    def __init__(self, db: MongoDB):
        self.db = db
        self.sources = NEWS_SOURCES
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def scrape_all_sources(self):
        """Scrape all configured news sources in parallel."""
        logger.info(f"Starting to scrape {len(self.sources)} news sources")
        
        tasks = []
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for source in self.sources:
                tasks.append(self.scrape_source(session, source))
            
            # Wait for all scraping tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        total_articles = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error during scraping: {result}")
            else:
                total_articles += result
        
        logger.info(f"Scraped a total of {total_articles} articles from all sources")
        return total_articles

    async def scrape_source(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> int:
        """Scrape a single news source for articles."""
        source_name = source["name"]
        source_url = source["url"]
        
        logger.info(f"Scraping {source_name} from {source_url}")
        
        try:
            # Fetch the main page
            async with session.get(source_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch {source_url}, status: {response.status}")
                    return 0
                
                html = await response.text()
            
            # Parse the main page for article links
            soup = BeautifulSoup(html, "html.parser")
            article_links = self._extract_article_links(soup, source, source_url)
            
            logger.info(f"Found {len(article_links)} article links on {source_name}")
            
            # Process each article (limited to 10 per source to prevent overloading)
            article_tasks = []
            for link in article_links[:10]:
                # Add a small delay between requests to be polite
                await asyncio.sleep(1)
                article_tasks.append(self._process_article(session, link, source))
            
            # Wait for all article processing tasks to complete
            article_results = await asyncio.gather(*article_tasks, return_exceptions=True)
            
            # Count successful articles
            successful_articles = sum(1 for r in article_results if r and not isinstance(r, Exception))
            logger.info(f"Successfully processed {successful_articles} articles from {source_name}")
            
            return successful_articles
            
        except Exception as e:
            logger.error(f"Error scraping {source_name}: {e}")
            return 0

    def _extract_article_links(self, soup: BeautifulSoup, source: Dict[str, str], base_url: str) -> List[str]:
        """Extract article links from the main page."""
        article_links = []
        
        # Find all article elements based on the source-specific selector
        article_selector = source.get("article_selector", "article")
        article_elements = soup.select(article_selector)
        
        for element in article_elements:
            # Look for links within the article element
            link_tag = element.find("a")
            if link_tag and link_tag.has_attr("href"):
                href = link_tag["href"]
                
                # Handle relative URLs
                if not href.startswith(("http://", "https://")):
                    href = urljoin(base_url, href)
                
                article_links.append(href)
        
        # If we couldn't find any links via the article selector, try a more general approach
        if not article_links:
            # Look for all links that might point to articles
            for link in soup.find_all("a", href=True):
                href = link["href"]
                
                # Handle relative URLs
                if not href.startswith(("http://", "https://")):
                    href = urljoin(base_url, href)
                
                # Filter URLs that look like article links (containing /article/, /news/, etc.)
                if re.search(r"/(article|news|story|sport)/", href):
                    article_links.append(href)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(article_links))

    async def _process_article(self, session: aiohttp.ClientSession, url: str, source: Dict[str, str]) -> bool:
        """Process a single article URL."""
        try:
            # Fetch the article page
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch article {url}, status: {response.status}")
                    return False
                
                html = await response.text()
            
            # Parse the article content
            soup = BeautifulSoup(html, "html.parser")
            
            # Extract article data using source-specific selectors
            title = self._extract_with_selector(soup, source.get("title_selector", "h1"))
            content = self._extract_with_selector(soup, source.get("content_selector", "article"))
            date_str = self._extract_with_selector(soup, source.get("date_selector", "time"))
            
            # Skip if we couldn't extract essential data
            if not title or not content:
                logger.warning(f"Could not extract title or content from {url}")
                return False
            
            # Record the current time for scraping timestamp
            scrape_time = datetime.now()
            
            # Parse publication date - explicitly use scrape time if date not found or parsing fails
            if date_str:
                publication_date = self._parse_date(date_str)
                if publication_date is None:
                    logger.info(f"Could not parse date '{date_str}', using scrape time instead")
                    publication_date = scrape_time
            else:
                logger.info(f"No date found for article, using scrape time")
                publication_date = scrape_time
            
            # Create a RawArticle object
            article = RawArticle(
                title=title,
                content=content,
                url=url,
                source=source["name"],
                publication_date=publication_date,
                html_content=html
            )
            
            # Save to database
            self.db.save_raw_article(article.to_dict())
            logger.debug(f"Saved article: {title}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing article {url}: {e}")
            return False

    def _extract_with_selector(self, soup: BeautifulSoup, selector: str) -> str:
        """Extract text using a CSS selector."""
        if not selector:
            return ""
        
        element = soup.select_one(selector)
        if not element:
            return ""
        
        # Return text with normalized whitespace
        return re.sub(r'\s+', ' ', element.get_text(strip=True))

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string into a datetime object."""
        if not date_str:
            return None
        
        # Try common date formats
        date_formats = [
            "%Y-%m-%dT%H:%M:%S",  # ISO format
            "%Y-%m-%d %H:%M:%S",
            "%B %d, %Y",          # January 1, 2023
            "%d %B %Y",           # 1 January 2023
            "%m/%d/%Y",           # MM/DD/YYYY
            "%d/%m/%Y",           # DD/MM/YYYY
            "%Y-%m-%d"            # YYYY-MM-DD
        ]
        
        # Clean up the date string
        date_str = re.sub(r'\s+', ' ', date_str.strip())
        
        # Try each format
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # If all formats fail, try to extract a date using regex
        date_pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
        match = re.search(date_pattern, date_str)
        if match:
            day, month, year = match.groups()
            # Handle two-digit years
            if len(year) == 2:
                year = "20" + year if int(year) < 50 else "19" + year
            try:
                return datetime(int(year), int(month), int(day))
            except ValueError:
                pass
        
        # If all else fails, return None (caller will use scrape time)
        logger.warning(f"Could not parse date: {date_str}")
        return None


async def scrape_news(db: MongoDB = None):
    """Main function to scrape news from all sources."""
    try:
        # Create a new database connection if not provided
        should_close_db = False
        if db is None:
            db = MongoDB()
            should_close_db = True
        
        # Create and run the scraper
        scraper = NewsScraper(db)
        total_articles = await scraper.scrape_all_sources()
        
        logger.success(f"News scraping completed. Total articles scraped: {total_articles}")
        
        # Close the database connection if we created it
        if should_close_db:
            db.close()
            
        return total_articles
        
    except Exception as e:
        logger.error(f"Error in scrape_news: {e}")
        return 0 