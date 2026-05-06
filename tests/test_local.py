import asyncio
import sys
import os

# Add src to path for local testing
sys.path.append(os.path.join(os.getcwd(), 'src'))

from sitewise_crawler import SPACrawler, CrawlerConfig

async def test_crawl():
    print("🚀 Starting test crawl...")
    config = CrawlerConfig(
        start_url="https://www.google.com", # Fast, traditional site
        max_depth=1,
        max_pages=2,
        use_playwright=False # Keep it fast for testing
    )
    
    crawler = SPACrawler(config)
    
    def on_page(page):
        print(f"DEBUG: Processed {page.url}")
        
    crawler.on_page_crawled = on_page
    
    result = await crawler.crawl()
    
    print(f"\nSummary:")
    print(f"Success: {result.success}")
    print(f"Pages: {result.total_pages}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    
    if result.success:
        for p in result.pages_all:
            print(f"- {p.url} ({p.title})")

if __name__ == "__main__":
    asyncio.run(test_crawl())
