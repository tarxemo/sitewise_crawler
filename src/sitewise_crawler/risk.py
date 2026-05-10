from typing import Optional
from pydantic import BaseModel, Field


class URLRiskResult(BaseModel):
    """
    Structured, portable representation of a URL risk assessment.
    Used as the contract between the crawler library and backend caches.
    """
    status: str = "Safe"  # Safe | Suspicious | Blocked
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    category: str = "Unknown"
    nsfw_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    source: str = "ai"  # classifier | ai | fallback | error

    @classmethod
    def from_dict(cls, data: dict) -> "URLRiskResult":
        """Build from the raw dict returned by InsightEngine.quick_url_risk."""
        return cls(
            status=data.get("status", "Safe"),
            risk_score=data.get("risk_score", 0.0),
            category=data.get("category", "Unknown"),
            nsfw_probability=data.get("nsfw_probability", 0.0),
            reason=data.get("reason", ""),
            source=data.get("source", "ai"),
        )

    def to_cache_dict(self) -> dict:
        """
        Flatten into a dict suitable for Django ORM `update_or_create` / `create`
        on a URLRiskCache-style model.
        """
        return {
            "risk_status": self.status,
            "risk_score": self.risk_score,
            "category": self.category,
            "nsfw_prob": self.nsfw_probability,
            "reason": self.reason,
            "source": self.source,
        }
