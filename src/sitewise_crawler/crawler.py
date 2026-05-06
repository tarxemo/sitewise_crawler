import asyncio
import logging
import time
from collections import deque
from typing import Set, List, Optional, Callable
from .models import CrawlerConfig, PageData, CrawlResult
from .fetchers import RequestsFetcher, PlaywrightFetcher
from .extractors import LinkExtractor, ContentExtractor, SPADetector

logger = logging.getLogger(__name__)

class SPACrawler:
    """
    Advanced Crawler Engine that automatically handles SPAs and traditional websites.
    """
    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.visited: Set[str] = set()
        self.queue = deque([(config.start_url, 0)])
        self.results: List[PageData] = []
        self.failed_urls: List[str] = []
        
        self.requests_fetcher = RequestsFetcher()
        self.playwright_fetcher = PlaywrightFetcher()
        
        # User-defined hook for page processing
        self.on_page_crawled: Optional[Callable[[PageData], None]] = None

    def _should_crawl(self, url: str, depth: int) -> bool:
        if url in self.visited:
            return False
        if depth > self.config.max_depth:
            return False
        if len(self.results) >= self.config.max_pages:
            return False
        if self.config.allowed_domains and not LinkExtractor.is_same_domain(url, self.config.start_url):
            return False
        return True

    async def crawl(self) -> CrawlResult:
        """Starts the full BFS crawling process based on config."""
        start_time = time.time()
        logger.info(f"Starting crawl for {self.config.start_url}")

        while self.queue and len(self.results) < self.config.max_pages:
            url, depth = self.queue.popleft()
            
            if not self._should_crawl(url, depth):
                continue
            
            self.visited.add(url)
            
            # Step 1: Extract the page
            page_data = await self.scrape_page(url, depth=depth)
            
            if not page_data:
                self.failed_urls.append(url)
                continue
            
            self.results.append(page_data)
            
            # Callback
            if self.on_page_crawled:
                self.on_page_crawled(page_data)
            
            # Step 2: Add new links to queue (only if we haven't hit max depth)
            if depth < self.config.max_depth:
                for link in page_data.links:
                    if LinkExtractor.is_same_domain(link, self.config.start_url):
                        self.queue.append((link, depth + 1))
            
            # Rate limiting
            await asyncio.sleep(self.config.rate_limit_delay)

        # Cleanup
        await self.playwright_fetcher.close()
        
        duration = time.time() - start_time
        return CrawlResult(
            success=len(self.results) > 0,
            pages_all=self.results,
            failed_urls=self.failed_urls,
            duration_seconds=duration,
            total_pages=len(self.results)
        )

    async def scrape_page(self, url: str, depth: int = 0) -> Optional[PageData]:
        """
        Directly extracts data from a single URL. 
        Supports HTML, SPAs, PDFs, and Word Documents.
        """
        logger.info(f"Scraping page: {url}")
        
        # Step 1: Fetch content
        # We start with Requests for efficiency and document handling
        content, status, title, content_type = await self.requests_fetcher.fetch(url, self.config)
        
        if not content:
            return None
            
        is_spa = False
        is_binary = False
        
        # Step 2: Handle based on content type
        if 'html' in content_type:
            # Check for SPA
            if SPADetector.is_spa(content) and self.config.use_playwright:
                logger.info(f"SPA detected for {url}, switching to Playwright")
                is_spa = True
                content, status, title, content_type = await self.playwright_fetcher.fetch(url, self.config)
            
            # Extract HTML content
            text_content = ContentExtractor.clean_text(content)
            links = LinkExtractor.extract_links(content, url)
        else:
            # Handle binary documents
            logger.info(f"Binary document detected ({content_type}) for {url}")
            is_binary = True
            text_content = ContentExtractor.extract_from_binary(content, content_type)
            links = [] # Binary files usually don't have crawlable links for our BFS
            
        return PageData(
            url=url,
            title=title or url.split('/')[-1],
            content=text_content,
            html=content if (isinstance(content, str) and self.config.max_pages < 10) else None,
            depth=depth,
            status_code=status,
            is_spa=is_spa,
            links=links,
            metadata={'content_type': content_type, 'is_binary': is_binary}
        )
