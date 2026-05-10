from .crawler import SPACrawler
from .models import CrawlerConfig, PageData, CrawlResult, UserInsight, CategoryScore, Entity
from .fetchers import RequestsFetcher, PlaywrightFetcher
from .extractors import LinkExtractor, ContentExtractor, SPADetector, DomainClassifier
from .analyzer import InsightEngine
from .behavior import BehaviorProfileSnapshot, CategoryEntry, ProfileBlender
from .policies import PolicySuggestion, PolicyEngine
from .risk import URLRiskResult
from .utils import create_insight_engine, get_env_api_key
from .domain_filter import (
    DomainFilter,
    normalize_domain,
    extract_domain,
    is_url_blocked,
    strip_blocked_urls,
)
# ── New modules (v0.2.0) ──────────────────────────────────────────────
from .session_analyzer import SessionEvent, SessionWindow, SessionSummary, SessionAnalyzer
from .alert_engine import (
    Alert, AlertContext, AlertEngine, Severity,
    BaseAlertRule,
    NSFWAlertRule, HighRiskSessionAlertRule,
    LowProductivityAlertRule, SuddenSpikeAlertRule, OffHoursAlertRule,
)
from .report_builder import (
    ReportSection, BehaviorReport, ReportBuilder,
    JSONReportExporter, TextReportExporter, PDFReportExporter,
)

__version__ = "0.2.0"
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
    "DomainClassifier",
    # Behavioral Intelligence (Loosely Coupled)
    "BehaviorProfileSnapshot",
    "CategoryEntry",
    "ProfileBlender",
    "PolicySuggestion",
    "PolicyEngine",
    "URLRiskResult",
    # Intelligence Engine & Factory
    "InsightEngine",
    "create_insight_engine",
    "get_env_api_key",
    # Domain Filtering (Loosely Coupled)
    "DomainFilter",
    "normalize_domain",
    "extract_domain",
    "is_url_blocked",
    "strip_blocked_urls",
    # ── Session Analysis (v0.2.0) ─────────────────────────
    "SessionEvent",
    "SessionWindow",
    "SessionSummary",
    "SessionAnalyzer",
    # ── Alert Engine (v0.2.0) ─────────────────────────────
    "Alert",
    "AlertContext",
    "AlertEngine",
    "Severity",
    "BaseAlertRule",
    "NSFWAlertRule",
    "HighRiskSessionAlertRule",
    "LowProductivityAlertRule",
    "SuddenSpikeAlertRule",
    "OffHoursAlertRule",
    # ── Report Builder (v0.2.0) ───────────────────────────
    "ReportSection",
    "BehaviorReport",
    "ReportBuilder",
    "JSONReportExporter",
    "TextReportExporter",
    "PDFReportExporter",
]
