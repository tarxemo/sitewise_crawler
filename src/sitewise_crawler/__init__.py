from .crawler import SPACrawler
from .models import CrawlerConfig, PageData, CrawlResult, UserInsight, CategoryScore
from .fetchers import RequestsFetcher, PlaywrightFetcher
from .extractors import LinkExtractor, ContentExtractor, SPADetector
from .analyzer import InsightEngine

__version__ = "0.1.0"
__all__ = [
    "SPACrawler",
    "CrawlerConfig",
    "PageData",
    "CrawlResult",
    "UserInsight",
    "CategoryScore",
    "RequestsFetcher",
    "PlaywrightFetcher",
    "LinkExtractor",
    "ContentExtractor",
    "SPADetector",
    "InsightEngine",
]
