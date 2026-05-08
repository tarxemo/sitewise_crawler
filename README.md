# Sitewise Crawler 🕷️🧠

[![Version](https://img.shields.io/pypi/v/sitewise-crawler)](https://pypi.org/project/sitewise-crawler/)
[![License](https://img.shields.io/github/license/tarxemo/sitewise-crawler)](https://github.com/tarxemo/sitewise-crawler/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/sitewise-crawler)](https://pypi.org/project/sitewise-crawler/)

**Sitewise Crawler** is an advanced, production-ready web crawling and behavioral analysis engine. It doesn't just scrape text; it understands it. Designed for institutional analytics, student well-being platforms, and high-security environments, it combines headless browser technology with LLM-powered insights.

## ✨ Key Features

- 🚀 **Hybrid Rendering**: Automatically detects SPAs (React, Vue, Angular, Next.js) and switches from fast `Requests` to full `Playwright` rendering only when needed.
- 🧠 **AI Insight Engine**: Integrated with **Groq (Llama 3.3)** to provide deep behavioral profiles, sentiment analysis, and intent estimation.
- 📄 **Multiformat Support**: Seamlessly extracts text from **HTML, PDF, and Microsoft Word (.docx)** documents.
- 🛡️ **Institutional Risk Assessment**: Real-time URL classification and NSFW detection using a hybrid of local domain databases and AI analysis.
- 🔗 **Intelligent Extraction**: Uses `trafilatura` for high-quality content extraction, stripping away headers, footers, and advertisements.
- ⚙️ **Production Ready**: Full async support, Pydantic validation, and synchronous wrappers for easy integration into Django, Flask, or FastAPI.

---

## 📦 Installation

```bash
pip install sitewise-crawler

# Install Playwright browsers (required for SPA support)
playwright install chromium
```

---

## 🚀 Quick Start: Web Crawling

Extract content from a website with automatic SPA detection.

```python
import asyncio
from sitewise_crawler import SPACrawler, CrawlerConfig

async def main():
    # 1. Configure the crawler
    config = CrawlerConfig(
        start_url="https://example.com",
        max_depth=2,
        max_pages=5,
        use_playwright=True
    )

    # 2. Run the crawler
    crawler = SPACrawler(config)
    result = await crawler.crawl()

    # 3. Access results
    for page in result.pages_all:
        print(f"URL: {page.url}")
        print(f"Title: {page.title}")
        print(f"Content Preview: {page.content[:100]}...")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧠 Advanced: AI Behavioral Analysis

The `InsightEngine` uses LLMs to analyze what a user is reading and provide a deep behavioral profile. This is ideal for monitoring student productivity or employee well-being.

```python
from sitewise_crawler import InsightEngine

# Initialize with your Groq API Key
engine = InsightEngine(api_key="your_groq_api_key")

# Analyze a list of URLs visited by a user
insight = engine.analyze_user_behavior_sync(
    user_id="user_123",
    urls=[
        "https://docs.python.org/3/",
        "https://stackoverflow.com/questions/...",
        "https://github.com/trending"
    ]
)

print(f"Primary Interests: {insight.primary_interests}")
print(f"Productivity Rating: {insight.productivity_rating}")
print(f"Sentiment: {insight.overall_sentiment}")
print(f"Behavioral Summary: {insight.behavioral_summary}")
```

### 🛡️ Real-time URL Risk Scorer

Instantly check if a URL is safe, suspicious, or inappropriate.

```python
risk = await engine.quick_url_risk("https://example-risky-site.com")

# Output:
# {
#   "status": "Blocked",
#   "risk_score": 0.95,
#   "category": "NSFW",
#   "reason": "Detected adult content patterns in page metadata.",
#   "source": "ai"
# }
```

---

## ⚙️ Configuration Options (`CrawlerConfig`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_url` | `str` | *Required* | The entry point for the crawler. |
| `max_depth` | `int` | `3` | Maximum BFS depth. |
| `max_pages` | `int` | `100` | Stop crawling after this many pages. |
| `use_playwright` | `bool` | `False` | Enable browser rendering for SPAs. |
| `rate_limit_delay` | `float` | `1.0` | Seconds to wait between requests. |
| `allowed_domains` | `List[str]` | `[]` | Only crawl links within these domains. |
| `js_wait_time` | `int` | `2000` | MS to wait for JS to render in Playwright. |

---

## 📊 Data Models

Sitewise Crawler uses Pydantic for strict typing. Key models include:

- **`PageData`**: Contains `url`, `title`, `content` (cleaned text), `html` (raw), and `metadata`.
- **`UserInsight`**: A comprehensive profile including `primary_interests`, `top_entities`, `sentiment_score`, `focus_score`, and `actionable_recommendation`.

---

## 🤝 Integration with Django/Flask

For synchronous environments like Django views, use the `_sync` methods provided:

```python
# In a Django View
def user_activity_report(request):
    engine = InsightEngine(api_key=settings.GROQ_API_KEY)
    urls = request.user.history.all().values_list('url', flat=True)
    
    insight = engine.analyze_user_behavior_sync(request.user.id, list(urls))
    return JsonResponse(insight.dict())
```

---

## 📄 License

This project is licensed under the MIT License. Developed and maintained by **TarXemo**.
