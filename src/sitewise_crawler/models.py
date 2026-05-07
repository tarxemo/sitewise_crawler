from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

class CrawlerConfig(BaseModel):
    """Configuration for the Crawler engine."""
    start_url: str
    max_depth: int = Field(default=3, ge=0)
    max_pages: int = Field(default=100, ge=1)
    concurrency: int = Field(default=3, ge=1)
    timeout_ms: int = Field(default=30000, ge=1000)
    rate_limit_delay: float = Field(default=1.0, ge=0.0)
    
    # SPA Settings (Disabled by default to avoid heavy browser dependencies)
    use_playwright: bool = False
    headless: bool = True
    wait_for_selector: Optional[str] = None
    js_wait_time: int = 2000
    
    # Filtering
    allowed_domains: List[str] = []
    ignore_patterns: List[str] = [
        r"\.(css|js|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$",
        r"^javascript:",
        r"^mailto:",
        r"^tel:",
    ]
    
    # Custom Headers
    user_agent: str = "SitewiseCrawler/0.1.1 (+https://github.com/tarxemo/sitewise-crawler)"

    @classmethod
    def for_single_url(cls, url: str, **kwargs) -> "CrawlerConfig":
        """
        Factory shortcut for analyzing a single page without BFS crawling.
        Ideal for on-demand URL risk assessment.
        """
        return cls(start_url=url, max_pages=1, max_depth=0, **kwargs)

class PageData(BaseModel):
    """Data extracted from a single page."""
    url: str
    title: Optional[str] = None
    content: str
    html: Optional[str] = None
    depth: int
    status_code: int
    is_spa: bool = False
    metadata: Dict[str, Any] = {}
    links: List[str] = []
    timestamp: datetime = Field(default_factory=datetime.now)

class CrawlResult(BaseModel):
    """Summary result of a crawl session."""
    success: bool
    pages_all: List[PageData]
    failed_urls: List[str]
    duration_seconds: float
    total_pages: int

class CategoryScore(BaseModel):
    category: str
    score: float  # 0.0 to 1.0

class Entity(BaseModel):
    name: str
    type: str  # Person, Organization, Location, Product, Concept
    frequency: int

class UserInsight(BaseModel):
    """Advanced behavioral analysis based on content consumed. Highly detailed for institutional use."""
    user_id: str
    analyzed_at: datetime = Field(default_factory=datetime.now)
    total_urls_analyzed: int
    
    # --- Core Content Analysis ---
    primary_interests: List[str] = []
    top_categories: List[CategoryScore] = []
    content_languages: List[str] = []
    content_complexity_score: float = 0.0  # 0 to 1 (Simple vs Academic/Professional)
    technical_proficiency_level: str = "Unknown"  # Beginner, Intermediate, Advanced, Expert
    
    # --- Sentiment & Psychological Indicators ---
    overall_sentiment: str  # Positive, Neutral, Negative, Mixed
    average_sentiment_score: float  # -1.0 to 1.0
    stress_or_anxiety_indicators: float = 0.0  # 0 to 1 (Useful for student/employee wellbeing)
    
    # --- Behavioral & Productivity Insights ---
    estimated_intent: str  # Research, Information, Entertainment, Transactional, Social
    productivity_rating: float = 0.0  # 0 to 1
    time_wasting_probability: float = 0.0  # 0 to 1 (High if consuming excessive social media/entertainment)
    focus_score: float = 0.0 # 0 to 1 (Is browsing highly concentrated or scattered?)
    
    # --- Academic & Career Alignment ---
    educational_alignment: float = 0.0  # 0 to 1
    academic_relevance_score: float = 0.0 # 0 to 1
    career_development_focus: float = 0.0 # 0 to 1
    
    # --- Commercial Intent ---
    shopping_intent_score: float = 0.0 # 0 to 1
    likely_in_market_for: List[str] = []
    
    # --- Extracted Entities ---
    top_entities: List[Entity] = []
    
    # --- Institutional Risk Assessment ---
    risk_assessment_summary: Optional[str] = None
    nsfw_or_inappropriate_probability: float = 0.0 # 0 to 1
    
    # --- AI Synthesized Summaries ---
    behavioral_summary: str
    actionable_recommendation: Optional[str] = None # E.g., "User might need study resources for Python"
    
    raw_ai_response: Optional[Dict[str, Any]] = None
