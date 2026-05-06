from .crawler import SPACrawler
from .models import CrawlerConfig, PageData, CrawlResult, UserInsight, CategoryScore, Entity
from .fetchers import RequestsFetcher, PlaywrightFetcher
from .extractors import LinkExtractor, ContentExtractor, SPADetector, DomainClassifier
from .analyzer import InsightEngine

__version__ = "0.1.2"
__all__ = [
    # Core Crawling
    "SPACrawler",
    "CrawlerConfig",
    "PageData",
    "CrawlResult",
    # Analysis Models
    "UserInsight",
    "CategoryScore",
    "Entity",
    # Fetchers
    "RequestsFetcher",
    "PlaywrightFetcher",
    # Extractors & Classifiers
    "LinkExtractor",
    "ContentExtractor",
    "SPADetector",
    "DomainClassifier",   # NEW: fast domain category lookup
    # Intelligence Engine
    "InsightEngine",      # Now has sync wrappers + quick_url_risk()
]
