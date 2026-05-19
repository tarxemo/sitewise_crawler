import logging
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from groq import Groq
from .crawler import SPACrawler
from .models import CrawlerConfig, UserInsight, CategoryScore, PageData

logger = logging.getLogger(__name__)


class InsightEngine:
    """
    Advanced engine for analyzing user behavior based on visited web content.
    
    The InsightEngine serves as the high-level orchestrator for behavioral
    intelligence. It integrates web crawling (via SPACrawler), content 
    extraction (via Trafilatura), and Large Language Model processing (via Groq)
    to transform raw URLs into a structured behavioral profile.
    
    Architecture:
    1.  **Extraction**: Fetches and sanitizes content from a batch of URLs.
    2.  **Consolidation**: Normalizes and chunks text to optimize LLM context usage.
    3.  **Synthesis**: Uses Zero-Shot classification and multi-dimensional analysis 
        to compute productivity, sentiment, and intent.
    """
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model

    # ─────────────────────────────────────────────────────────────
    # PRIMARY ASYNC API
    # ─────────────────────────────────────────────────────────────

    async def analyze_user_behavior(
        self,
        user_id: str,
        urls: List[str],
        crawler_config: Optional[CrawlerConfig] = None
    ) -> UserInsight:
        """
        Executes a full-spectrum behavioral analysis for a specific user.
        
        This method performs a deep-crawl of the provided URLs, extracts 
        the semantic core of each page, and triggers the AI analysis pipeline.
        
        Args:
            user_id: Unique identifier for the subject being analyzed.
            urls: A list of URL strings representing the user's browsing history.
            crawler_config: Optional configuration for the scraping engine (depth, timeout, etc.)
            
        Returns:
            A `UserInsight` object containing multidimensional behavioral metrics 
            ranging from productivity scores to psychological well-being indicators.
        """
        logger.info(f"Starting behavioral analysis for user {user_id} with {len(urls)} URLs")

        # 1. Scrape all URLs
        if not crawler_config:
            crawler_config = CrawlerConfig(start_url=urls[0], max_pages=len(urls), max_depth=0)

        crawler = SPACrawler(crawler_config)

        tasks = [crawler.scrape_page(url) for url in urls]
        pages: List[PageData] = await asyncio.gather(*tasks)
        pages = [p for p in pages if p is not None]

        if not pages:
            raise ValueError("No content could be extracted from the provided URLs.")

        # 2. Consolidate content — take chunks to stay within LLM context limits
        consolidated_content = ""
        for page in pages:
            preview = page.content[:1500]
            consolidated_content += f"\n--- URL: {page.url} ---\nTitle: {page.title}\nContent: {preview}\n"

        # 3. Perform AI Analysis
        analysis_result = await self._call_ai_analyzer(consolidated_content)

        # 4. Construct UserInsight model
        from .models import Entity
        return UserInsight(
            user_id=user_id,
            total_urls_analyzed=len(pages),
            primary_interests=analysis_result.get("primary_interests", []),
            top_categories=[
                CategoryScore(category=c["name"], score=c["score"])
                for c in analysis_result.get("top_categories", [])
            ],
            content_languages=analysis_result.get("content_languages", []),
            content_complexity_score=analysis_result.get("content_complexity_score", 0.0),
            technical_proficiency_level=analysis_result.get("technical_proficiency_level", "Unknown"),
            overall_sentiment=analysis_result.get("overall_sentiment", "Neutral"),
            average_sentiment_score=analysis_result.get("average_sentiment_score", 0.0),
            stress_or_anxiety_indicators=analysis_result.get("stress_or_anxiety_indicators", 0.0),
            estimated_intent=analysis_result.get("estimated_intent", "Unknown"),
            productivity_rating=analysis_result.get("productivity_rating", 0.0),
            time_wasting_probability=analysis_result.get("time_wasting_probability", 0.0),
            focus_score=analysis_result.get("focus_score", 0.0),
            educational_alignment=analysis_result.get("educational_alignment", 0.0),
            academic_relevance_score=analysis_result.get("academic_relevance_score", 0.0),
            career_development_focus=analysis_result.get("career_development_focus", 0.0),
            shopping_intent_score=analysis_result.get("shopping_intent_score", 0.0),
            likely_in_market_for=analysis_result.get("likely_in_market_for", []),
            top_entities=[
                Entity(**e) for e in analysis_result.get("top_entities", [])
            ],
            risk_assessment_summary=analysis_result.get("risk_assessment_summary"),
            nsfw_or_inappropriate_probability=analysis_result.get("nsfw_or_inappropriate_probability", 0.0),
            behavioral_summary=analysis_result.get("behavioral_summary", "No summary available."),
            actionable_recommendation=analysis_result.get("actionable_recommendation"),
            raw_ai_response=analysis_result
        )

    # ─────────────────────────────────────────────────────────────
    # SYNC WRAPPER — Safe for use in Django views & mutations
    # ─────────────────────────────────────────────────────────────

    def analyze_user_behavior_sync(
        self,
        user_id: str,
        urls: List[str],
        crawler_config: Optional[CrawlerConfig] = None
    ) -> UserInsight:
        """
        Synchronous wrapper for use in Django/Flask views and GraphQL mutations.
        Safely handles both inside-event-loop and standalone contexts.
        """
        try:
            asyncio.get_running_loop()
            # Inside an existing event loop — run in a separate thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.analyze_user_behavior(user_id, urls, crawler_config)
                )
                return future.result()
        except RuntimeError:
            # No running event loop — safe to call asyncio.run() directly
            return asyncio.run(self.analyze_user_behavior(user_id, urls, crawler_config))

    # ─────────────────────────────────────────────────────────────
    # FAST SINGLE-URL RISK SCORER
    # ─────────────────────────────────────────────────────────────

    async def quick_url_risk(self, url: str) -> Dict[str, Any]:
        """
        Fast, single-URL risk assessment designed for real-time use.

        Strategy:
          1. Check DomainClassifier first (instant, zero network).
          2. If domain is unknown, scrape the page and ask AI for a lightweight
             risk assessment (much cheaper than a full behavioral profile).

        Returns:
            {
                "status":           "Safe" | "Suspicious" | "Blocked",
                "risk_score":       0.0 – 1.0,
                "category":         "Entertainment" | "NSFW" | "Development" | ...,
                "nsfw_probability": 0.0 – 1.0,
                "reason":           "One-sentence explanation",
                "source":           "classifier" | "ai" | "fallback" | "error"
            }
        """
        from .extractors import DomainClassifier

        # ── Step 1: instant known-domain lookup ──
        category = DomainClassifier.classify(url)
        if category is not None:
            risk_score = DomainClassifier.get_risk_score(url)
            is_nsfw = category == "NSFW"
            status = "Blocked" if is_nsfw else ("Suspicious" if risk_score >= 0.3 else "Safe")
            return {
                "status":           status,
                "risk_score":       risk_score,
                "category":         category,
                "nsfw_probability": 1.0 if is_nsfw else 0.0,
                "reason":           f"Known domain classified as {category}.",
                "source":           "classifier",
            }

        # ── Step 2: scrape + lightweight AI risk call ──
        try:
            config = CrawlerConfig.for_single_url(url, use_playwright=False)
            crawler = SPACrawler(config)
            page = await crawler.scrape_page(url)
            await crawler.playwright_fetcher.close()

            if not page or not page.content:
                return {
                    "status": "Safe", "risk_score": 0.0, "category": "Unknown",
                    "nsfw_probability": 0.0, "reason": "Could not fetch page content.",
                    "source": "fallback",
                }

            content_preview = page.content[:2000]
            prompt = f"""
You are a URL Risk Assessment AI. Analyze this webpage content and return ONLY a JSON object:
{{
    "status": "Safe" | "Suspicious" | "Blocked",
    "risk_score": 0.0,
    "category": "single category label",
    "nsfw_probability": 0.0,
    "reason": "one sentence risk explanation",
    "behavioral_insight": "A short (max 10 words) insight into what this activity means for the user's profile (e.g., 'Researching microservices', 'Consuming technical news')"
}}

URL: {url}
Title: {page.title}
Content preview:
{content_preview}
"""
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a URL content risk classifier. Output strictly valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                response_format={"type": "json_object"},
                max_tokens=256,
            )
            result = json.loads(chat_completion.choices[0].message.content)
            result["source"] = "ai"
            return result

        except Exception as e:
            logger.error(f"quick_url_risk failed for {url}: {e}")
            return {
                "status": "Safe", "risk_score": 0.0, "category": "Unknown",
                "nsfw_probability": 0.0, "reason": f"Analysis error: {str(e)}",
                "source": "error",
            }

    def quick_url_risk_sync(self, url: str) -> Dict[str, Any]:
        """Synchronous wrapper for quick_url_risk. Safe for Django mutations."""
        try:
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.quick_url_risk(url)).result()
        except RuntimeError:
            return asyncio.run(self.quick_url_risk(url))

    # ─────────────────────────────────────────────────────────────
    # AI CORE
    # ─────────────────────────────────────────────────────────────

    async def _call_ai_analyzer(self, content: str) -> Dict[str, Any]:
        """Calls Groq to analyze consolidated browsing content and return a behavioral profile."""
        prompt = f"""
You are a highly advanced Behavioral Profiling AI working for an institutional analytics platform.
Analyze the following browsing history content and provide a highly detailed behavioral profile.
Return ONLY a JSON object exactly matching this structure:
{{
    "primary_interests": ["topic1", "topic2", "topic3"],
    "top_categories": [{{"name": "CategoryName", "score": 0.9}}],
    "content_languages": ["English"],
    "content_complexity_score": 0.8,
    "technical_proficiency_level": "Intermediate",
    "overall_sentiment": "Positive",
    "average_sentiment_score": 0.5,
    "stress_or_anxiety_indicators": 0.1,
    "estimated_intent": "Research",
    "productivity_rating": 0.85,
    "time_wasting_probability": 0.15,
    "focus_score": 0.9,
    "educational_alignment": 0.9,
    "academic_relevance_score": 0.8,
    "career_development_focus": 0.7,
    "shopping_intent_score": 0.0,
    "likely_in_market_for": [],
    "top_entities": [{{"name": "OpenAI", "type": "Organization", "frequency": 5}}],
    "risk_assessment_summary": "Low risk. Professional content.",
    "nsfw_or_inappropriate_probability": 0.0,
    "behavioral_summary": "A comprehensive paragraph summarizing habits.",
    "actionable_recommendation": "Suggest resource X based on interest Y."
}}

Content to analyze:
{content}
"""
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a specialized User Behavior Analyst. Output strictly valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"}
            )
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            return {
                "behavioral_summary": f"Failed to perform AI analysis: {str(e)}",
                "overall_sentiment": "Unknown"
            }
