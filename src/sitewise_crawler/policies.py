import logging
from typing import List, Dict, Set, Any, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from .extractors import DomainClassifier

logger = logging.getLogger(__name__)


class PolicySuggestion(BaseModel):
    """
    Portable representation of a smart policy suggestion.
    Backend-agnostic; can be consumed by Django ORM, Flask SQLAlchemy, or any storage layer.
    """
    domain: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    category: Optional[str] = None
    device_name: Optional[str] = None
    status: str = "pending"  # pending | accepted | dismissed


class PolicyEngine:
    """
    Stateless engine for generating domain-blocking suggestions based on
    behavioral profiles and visited-domain histories.
    """

    TIME_WASTING_THRESHOLD = 0.5
    HIGH_RISK_THRESHOLD = 0.8
    NSFW_CONFIDENCE = 0.98
    MAX_ENTERTAINMENT_CONFIDENCE = 0.9

    @staticmethod
    def extract_domains(urls: List[str]) -> Dict[str, int]:
        """
        Extract normalized domain names from a list of URLs.
        Returns a dict mapping domain → visit count.
        """
        visited_domains: Dict[str, int] = {}
        for url in urls:
            try:
                domain = urlparse(url).netloc.lower().replace("www.", "")
                if domain:
                    visited_domains[domain] = visited_domains.get(domain, 0) + 1
            except Exception:
                continue
        return visited_domains

    @classmethod
    def generate_suggestions(
        cls,
        visited_domains: Dict[str, int],
        behavior_profile: Dict[str, Any],
        already_suggested: Optional[Set[str]] = None,
        already_blocked: Optional[Set[str]] = None,
        device_name: Optional[str] = None,
    ) -> List[PolicySuggestion]:
        """
        Generate smart policy suggestions based on:
        - Domain category classification
        - Behavioral profile (time-wasting probability, NSFW indicators)
        - Already suggested / already blocked sets

        behavior_profile keys expected:
            - time_wasting_probability (float)
            - nsfw_probability (float)
        """
        already_suggested = already_suggested or set()
        already_blocked = already_blocked or set()

        time_wasting_prob = behavior_profile.get("time_wasting_probability", 0.0)
        nsfw_prob = behavior_profile.get("nsfw_probability", 0.0)

        new_suggestions: List[PolicySuggestion] = []

        for domain, count in visited_domains.items():
            if domain in already_suggested or domain in already_blocked:
                continue

            category = DomainClassifier.classify(f"https://{domain}")
            risk_score = DomainClassifier.get_risk_score(f"https://{domain}")

            # Rule 1: Known NSFW domains → always suggest block
            if category == "NSFW":
                new_suggestions.append(PolicySuggestion(
                    domain=domain,
                    reason=f"[{device_name or 'Device'}] Domain classified as NSFW.",
                    confidence=cls.NSFW_CONFIDENCE,
                    category=category,
                    device_name=device_name,
                ))
                continue

            # Rule 2: High-risk + high NSFW probability from AI
            if risk_score > cls.HIGH_RISK_THRESHOLD and nsfw_prob > 0.5:
                new_suggestions.append(PolicySuggestion(
                    domain=domain,
                    reason=f"[{device_name or 'Device'}] High risk content detected by AI.",
                    confidence=risk_score,
                    category=category or "High Risk",
                    device_name=device_name,
                ))
                continue

            # Rule 3: Time-wasting behavior on entertainment/social domains
            if time_wasting_prob > cls.TIME_WASTING_THRESHOLD and category in (
                "Social Media", "Entertainment", "Gaming"
            ):
                confidence = min(cls.MAX_ENTERTAINMENT_CONFIDENCE, time_wasting_prob + 0.2)
                new_suggestions.append(PolicySuggestion(
                    domain=domain,
                    reason=(
                        f"Spent significant time on {category} ({domain}). "
                        f"Productivity is {behavior_profile.get('productivity_rating', 0):.0%}. "
                        f"Suggest blocking to improve focus."
                    ),
                    confidence=round(confidence, 2),
                    category=category,
                    device_name=device_name,
                ))

        return new_suggestions

    @classmethod
    def should_auto_block(cls, risk_result: Dict[str, Any]) -> bool:
        """
        Quick heuristic to decide if a URL should be immediately flagged for blocking.
        Used by extensions or edge proxies that need instant decisions.
        """
        status = risk_result.get("status", "Safe")
        risk_score = risk_result.get("risk_score", 0.0)
        nsfw_prob = risk_result.get("nsfw_probability", 0.0)
        return status == "Blocked" or (risk_score > cls.HIGH_RISK_THRESHOLD and nsfw_prob > 0.5)
