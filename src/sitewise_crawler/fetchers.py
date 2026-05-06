import logging
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import requests
from bs4 import BeautifulSoup
from .models import CrawlerConfig

logger = logging.getLogger(__name__)

class BaseFetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str, config: CrawlerConfig) -> Tuple[Optional[Any], int, Optional[str], Optional[str]]:
        """
        Fetch content from a URL.
        Returns: (content, status_code, title, content_type)
        """
        pass

class RequestsFetcher(BaseFetcher):
    async def fetch(self, url: str, config: CrawlerConfig) -> Tuple[Optional[Any], int, Optional[str], Optional[str]]:
        try:
            headers = {"User-Agent": config.user_agent}
            response = requests.get(url, headers=headers, timeout=config.timeout_ms/1000, stream=True)
            content_type = response.headers.get('Content-Type', '').split(';')[0].lower()
            
            if response.status_code == 200:
                # Handle text-based content
                if 'html' in content_type or 'text' in content_type:
                    soup = BeautifulSoup(response.text, 'lxml')
                    title = soup.title.string if soup.title else ""
                    return response.text, response.status_code, title, content_type
                
                # Handle binary content (PDF, Docx, etc)
                return response.content, response.status_code, url.split('/')[-1], content_type
                
            return None, response.status_code, None, content_type
        except Exception as e:
            logger.error(f"RequestsFetcher error for {url}: {e}")
            return None, 0, None, None

class PlaywrightFetcher(BaseFetcher):
    def __init__(self):
        self.playwright = None
        self.browser = None

    async def _ensure_browser(self, config: CrawlerConfig):
        if not self.browser:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=config.headless)

    async def fetch(self, url: str, config: CrawlerConfig) -> Tuple[Optional[Any], int, Optional[str], Optional[str]]:
        try:
            await self._ensure_browser(config)
            context = await self.browser.new_context(user_agent=config.user_agent)
            page = await context.new_page()
            
            # Playwright is mainly for HTML/SPA, but it can handle navigation to documents
            response = await page.goto(url, wait_until="networkidle", timeout=config.timeout_ms)
            
            if not response:
                return None, 0, None, None
            
            content_type = response.headers.get('content-type', '').split(';')[0].lower()
            
            # If it's a binary file, Playwright might trigger a download or show a PDF viewer
            # For simplicity, we fallback to requests for binary files in the crawler engine,
            # but here we return what we can.
            if 'html' not in content_type:
                # Use raw response body for non-html
                content = await response.body()
                await context.close()
                return content, response.status, url.split('/')[-1], content_type

            import asyncio
            await asyncio.sleep(config.js_wait_time / 1000)
            
            if config.wait_for_selector:
                try:
                    await page.wait_for_selector(config.wait_for_selector, timeout=5000)
                except:
                    pass

            html = await page.content()
            status = response.status
            title = await page.title()
            
            await context.close()
            return html, status, title, content_type
        except Exception as e:
            logger.error(f"PlaywrightFetcher error for {url}: {e}")
            return None, 0, None, None

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
