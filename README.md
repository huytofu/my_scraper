# Sports Event Scraper and Highlighter

A robust system for scraping, processing, and highlighting sports events from multiple news sources.

## Overview

This system automatically:

1. Scrapes articles from 5 major sports news websites in parallel
2. Processes and extracts sports-related information from articles
3. Clusters articles that discuss the same sports event using NLP techniques
4. Selects the most important sports events for highlighting based on configured criteria
5. Runs on a schedule with separate processes at set times

## System Architecture

The system follows a pipeline architecture:

1. **Scraping Layer**
   - Parallel asynchronous scraping of 5 news sources
   - HTML parsing and content extraction
   - Raw article storage in MongoDB

2. **Processing Pipeline**
   - Sports type extraction
   - Named entity recognition
   - Text embedding generation
   - Feature storage in MongoDB

3. **Clustering Module**
   - Hierarchical clustering by sports type
   - Event identification and grouping
   - Cross-source event matching

4. **Highlight Selection Engine**
   - Event scoring based on:
     - Coverage (number of sources)
     - Freshness (recency of reporting)
     - Sports type importance (configurable weights)
   - Selection of top N events

5. **Scheduler**
   - Scraping every 3 hours
   - Processing right after scraping
   - Clustering and highlighting at noon and midnight

## Requirements

- Python 3.8+
- MongoDB
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/sports-event-scraper.git
   cd sports-event-scraper
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Download the spaCy language model:
   ```bash
   python -m spacy download en_core_web_sm
   ```

5. Create a `.env` file (use `.env.example` as a template):
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

## Configuration

Configuration settings are stored in `my_scraper/config/settings.py`. Key parameters include:

- **News Sources**: List of websites to scrape with their CSS selectors
- **Sports Importance**: Weights for different sports types
- **Clustering Parameters**: Distance threshold and model selection
- **Scheduling**: Intervals and times for various jobs

## Usage

### Running the Scheduler

```bash
python -m my_scraper.main --scheduler
```

### Running All Jobs Immediately

```bash
python -m my_scraper.main --run-now
```

### Running Individual Jobs

```bash
python -m my_scraper.main --job scrape   # Just scrape
python -m my_scraper.main --job process  # Just process
python -m my_scraper.main --job cluster  # Just cluster
python -m my_scraper.main --job highlight # Just highlight
```

## Project Structure

```
my_scraper/
├── config/             # Configuration settings
├── database/           # Database connection and models
├── models/             # Data models and classes
├── processing/         # Article processing and clustering
│   ├── processor.py    # NLP processing and feature extraction
│   └── highlighter.py  # Event scoring and highlight selection
├── scraper/            # Web scraping functionality
│   └── news_scraper.py # Parallel news source scraper
├── scheduler/          # Job scheduling and execution
│   └── jobs.py         # Scheduled job definitions
├── .env.example        # Example environment variables
├── main.py             # Main entry point
├── README.md           # Project documentation
└── requirements.txt    # Project dependencies
```

## Customization

### Adding New News Sources

Edit `my_scraper/config/settings.py` and add a new entry to the `NEWS_SOURCES` list:

```python
{
    "name": "New Source Name",
    "url": "https://newsource.com/sports",
    "article_selector": ".article-class",
    "title_selector": ".title-class",
    "content_selector": ".content-class",
    "date_selector": ".date-class"
}
```

### Adjusting Sports Importance

Edit the `SPORTS_IMPORTANCE` dictionary in `settings.py`:

```python
SPORTS_IMPORTANCE = {
    "football": 1.3,  # Increase importance
    "cricket": 0.7,   # Decrease importance
    # ...
}
```

## Monitoring

Logs are stored in the `logs/` directory with rotation enabled:

- `logs/sports_scraper_*.log` - Main application logs
- `logs/scheduler_*.log` - Scheduler-specific logs

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- BeautifulSoup4 for HTML parsing
- SpaCy for NLP processing
- SentenceTransformers for embedding generation
- MongoDB for storage
- Schedule for job scheduling 