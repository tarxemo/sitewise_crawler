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
    Advanced engine for analyzing user behavior based on visited content.
    Uses AI (Groq) to provide deep insights.
    """
    def __init__(self, api_key: str, model: str = "llama-3.1-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model

    async def analyze_user_behavior(
        self, 
        user_id: str, 
        urls: List[str], 
        crawler_config: Optional[CrawlerConfig] = None
    ) -> UserInsight:
        """
        Scrapes a list of URLs and performs intensive AI analysis on the content.
        """
        logger.info(f"Starting behavioral analysis for user {user_id} with {len(urls)} URLs")
        
        # 1. Scrape all URLs
        if not crawler_config:
            crawler_config = CrawlerConfig(start_url=urls[0], max_pages=len(urls))
            
        crawler = SPACrawler(crawler_config)
        
        tasks = [crawler.scrape_page(url) for url in urls]
        pages: List[PageData] = await asyncio.gather(*tasks)
        pages = [p for p in pages if p is not None]
        
        if not pages:
            raise ValueError("No content could be extracted from the provided URLs.")

        # 2. Consolidate content for analysis
        # We take chunks of content from each page to stay within LLM context limits
        consolidated_content = ""
        for page in pages:
            preview = page.content[:1500]  # Take first 1500 chars from each page
            consolidated_content += f"\n--- URL: {page.url} ---\nTitle: {page.title}\nContent: {preview}\n"

        # 3. Perform AI Analysis
        analysis_result = await self._call_ai_analyzer(consolidated_content)
        
        # 4. Construct UserInsight model
        from .models import Entity
        return UserInsight(
            user_id=user_id,
            total_urls_analyzed=len(pages),
            # Core
            primary_interests=analysis_result.get("primary_interests", []),
            top_categories=[
                CategoryScore(category=c["name"], score=c["score"]) 
                for c in analysis_result.get("top_categories", [])
            ],
            content_languages=analysis_result.get("content_languages", []),
            content_complexity_score=analysis_result.get("content_complexity_score", 0.0),
            technical_proficiency_level=analysis_result.get("technical_proficiency_level", "Unknown"),
            
            # Sentiment
            overall_sentiment=analysis_result.get("overall_sentiment", "Neutral"),
            average_sentiment_score=analysis_result.get("average_sentiment_score", 0.0),
            stress_or_anxiety_indicators=analysis_result.get("stress_or_anxiety_indicators", 0.0),
            
            # Behavior
            estimated_intent=analysis_result.get("estimated_intent", "Unknown"),
            productivity_rating=analysis_result.get("productivity_rating", 0.0),
            time_wasting_probability=analysis_result.get("time_wasting_probability", 0.0),
            focus_score=analysis_result.get("focus_score", 0.0),
            
            # Academic/Career
            educational_alignment=analysis_result.get("educational_alignment", 0.0),
            academic_relevance_score=analysis_result.get("academic_relevance_score", 0.0),
            career_development_focus=analysis_result.get("career_development_focus", 0.0),
            
            # Commercial
            shopping_intent_score=analysis_result.get("shopping_intent_score", 0.0),
            likely_in_market_for=analysis_result.get("likely_in_market_for", []),
            
            # Entities
            top_entities=[
                Entity(**e) for e in analysis_result.get("top_entities", [])
            ],
            
            # Risk
            risk_assessment_summary=analysis_result.get("risk_assessment_summary"),
            nsfw_or_inappropriate_probability=analysis_result.get("nsfw_or_inappropriate_probability", 0.0),
            
            # Summary
            behavioral_summary=analysis_result.get("behavioral_summary", "No summary available."),
            actionable_recommendation=analysis_result.get("actionable_recommendation"),
            raw_ai_response=analysis_result
        )

    async def _call_ai_analyzer(self, content: str) -> Dict[str, Any]:
        """Calls Groq to analyze the consolidated content."""
        prompt = f"""
        You are a highly advanced Behavioral Profiling AI working for an institutional analytics platform.
        Analyze the following browsing history content and provide a massive, highly detailed behavioral profile of the user.
        Return ONLY a JSON object exactly matching this structure (fill in the values based on your analysis):
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
                        "content": "You are a specialized User Behavior Analyst. You extract deep, multi-dimensional insights from web content history. Output strictly valid JSON."
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
