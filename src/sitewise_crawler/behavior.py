import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CategoryEntry(BaseModel):
    category: str
    score: float = 0.0


class BehaviorProfileSnapshot(BaseModel):
    """
    Portable, framework-agnostic representation of a device's behavioral state.
    Designed to be passed between the crawler library and any backend (Django, Flask, etc.)
    """
    total_urls: int = 0
    contributing_url_count: int = 0
    is_stale: bool = True

    primary_interests: List[str] = Field(default_factory=list)
    top_categories: List[CategoryEntry] = Field(default_factory=list)

    productivity_rating: float = 0.0
    focus_score: float = 0.0
    time_wasting_probability: float = 0.0
    stress_indicators: float = 0.0

    educational_alignment: float = 0.0
    academic_relevance: float = 0.0
    career_development: float = 0.0

    shopping_intent_score: float = 0.0
    likely_in_market_for: List[str] = Field(default_factory=list)

    overall_sentiment: str = "Unknown"
    nsfw_probability: float = 0.0
    risk_summary: Optional[str] = None

    behavioral_summary: str = ""
    actionable_recommendation: Optional[str] = None

    raw_ai_response: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        # Allow conversion from Django model instances via attribute access
        from_attributes = True


class ProfileBlender:
    """
    Stateless behavioral profile blending engine.
    
    The ProfileBlender is responsible for the mathematical synthesis of 
    behavioral scores. It implements incremental state updates, allowing a 
    long-term behavioral profile to evolve as new browsing data is ingested.
    
    Key Methodologies:
    1.  **Exponential Moving Average (EMA)**: Used for behavioral scores to 
        balance historical stability with recent behavioral shifts.
    2.  **Trend Analysis**: Calculates velocity to detect if a user's focus 
        or productivity is trending positively or negatively.
    3.  **Heuristic Classification**: Maps domain categories to numerical 
        productivity and focus weights.
    """

    PRODUCTIVE_CATEGORIES = {"Development", "Education", "Productivity", "News"}
    DISTRACTING_CATEGORIES = {"Social Media", "Entertainment", "Gaming", "Shopping"}
    MAX_INTERESTS = 15
    MAX_CATEGORIES = 10

    @staticmethod
    def blend(old_value: float, new_value: float, count: int, alpha: Optional[float] = None) -> float:
        """
        Incremental weighted average or Exponential Moving Average (EMA).
        If alpha is provided, uses EMA: alpha * new + (1 - alpha) * old.
        Otherwise uses simple cumulative average.
        """
        if count < 0:
            count = 0
        
        if alpha is not None:
            # EMA formula
            return round(alpha * new_value + (1 - alpha) * old_value, 3)
            
        # Standard incremental average
        return round((old_value * count + new_value) / (count + 1), 3)

    @classmethod
    def calculate_velocity(cls, old_value: float, new_value: float) -> float:
        """Computes the rate of change (velocity) between the old and new state."""
        return round(new_value - old_value, 4)

    @classmethod
    def compute_page_scores(cls, category: str, status: str, risk_score: float, nsfw_prob: float) -> Dict[str, float]:
        """
        Given a single URL's classification, compute the page-level behavioral scores.
        Returns a dict with keys: productivity, focus, time_waste, nsfw.
        """
        page_productivity = 0.5
        if status == "Safe":
            if category in cls.PRODUCTIVE_CATEGORIES:
                page_productivity = 0.9
            elif category in cls.DISTRACTING_CATEGORIES:
                page_productivity = 0.2

        page_focus = 1.0 if status == "Safe" else 0.0
        page_time_waste = 1.0 - page_productivity

        return {
            "productivity": page_productivity,
            "focus": page_focus,
            "time_waste": page_time_waste,
            "nsfw": nsfw_prob,
        }

    @classmethod
    def update_top_categories(
        cls,
        existing_categories: List[Dict[str, Any]],
        new_category: str,
        count: int
    ) -> List[Dict[str, Any]]:
        """
        Incrementally update the top-categories list with a newly observed category.
        Returns a new sorted list limited to MAX_CATEGORIES entries.
        """
        cats = [dict(c) for c in existing_categories]  # shallow copy
        found = False
        for c in cats:
            if c.get("category") == new_category:
                c["score"] = round((c["score"] * count + 1.0) / (count + 1), 3)
                found = True
                break

        if not found:
            cats.append({"category": new_category, "score": round(1.0 / (count + 1), 3)})

        cats.sort(key=lambda x: x["score"], reverse=True)
        return cats[: cls.MAX_CATEGORIES]

    @classmethod
    def update_primary_interests(
        cls,
        existing_interests: List[str],
        new_category: str
    ) -> List[str]:
        """Append a new category to primary interests if not already present and under limit."""
        interests = list(existing_interests)
        if new_category != "Unknown" and new_category not in interests and len(interests) < cls.MAX_INTERESTS:
            interests.append(new_category)
        return interests

    @classmethod
    def update_profile_from_risk(
        cls,
        profile: BehaviorProfileSnapshot,
        risk_result: Dict[str, Any]
    ) -> BehaviorProfileSnapshot:
        """
        Core loose-coupling method.
        Takes a profile snapshot and a risk-result dict (from InsightEngine.quick_url_risk),
        and returns a *new* updated BehaviorProfileSnapshot.
        """
        status = risk_result.get("status", "Safe")
        category = risk_result.get("category", "Unknown")
        risk_score = risk_result.get("risk_score", 0.0)
        nsfw_prob = risk_result.get("nsfw_probability", 0.0)

        n = profile.contributing_url_count

        page_scores = cls.compute_page_scores(category, status, risk_score, nsfw_prob)

        updated = profile.model_copy(deep=True)

        # Use a higher alpha (0.2) for risk/nsfw to react faster to threats
        # Use a lower alpha (0.05) for general behavioral scores for stability
        updated.productivity_rating = cls.blend(profile.productivity_rating, page_scores["productivity"], n, alpha=0.05)
        updated.focus_score = cls.blend(profile.focus_score, page_scores["focus"], n, alpha=0.05)
        updated.time_wasting_probability = cls.blend(
            profile.time_wasting_probability, page_scores["time_waste"], n, alpha=0.05
        )
        updated.nsfw_probability = cls.blend(profile.nsfw_probability, page_scores["nsfw"], n, alpha=0.2)

        # Trend detection logic
        prod_velocity = cls.calculate_velocity(profile.productivity_rating, updated.productivity_rating)
        risk_spike = page_scores["nsfw"] > 0.4 and (page_scores["nsfw"] - profile.nsfw_probability) > 0.2

        if risk_spike:
            updated.behavioral_summary = "⚠️ Sudden spike in high-risk content detected. " + (updated.behavioral_summary or "")
        
        # Incremental Summary Aggregation
        new_insight = risk_result.get("behavioral_insight")
        if new_insight:
            # If the profile was a mock/simulated one, clear it and start fresh with real data
            is_simulated = profile.raw_ai_response.get("simulated", False)
            if is_simulated:
                updated.behavioral_summary = f"Real-time monitoring active. Recent: {new_insight}."
                updated.raw_ai_response["simulated"] = False # Mark as no longer simulated
            else:
                # Append to existing summary, keeping it concise
                current_summary = profile.behavioral_summary or ""
                if len(current_summary) > 300: # Truncate if too long
                    current_summary = "..." + current_summary[-200:]
                updated.behavioral_summary = f"{current_summary}\n• {new_insight}."

        if category != "Unknown":
            updated.top_categories = cls.update_top_categories(
                profile.top_categories, category, n
            )
            updated.primary_interests = cls.update_primary_interests(
                profile.primary_interests, category
            )

        updated.contributing_url_count = profile.contributing_url_count + 1
        updated.total_urls = profile.total_urls + 1
        updated.is_stale = False
        
        # Store metadata for the panel to see the "intelligence" in action
        updated.raw_ai_response["last_velocity"] = prod_velocity
        updated.raw_ai_response["anomaly_detected"] = risk_spike

        return updated

    @classmethod
    def map_full_insight_to_snapshot(cls, insight: Any) -> BehaviorProfileSnapshot:
        """
        Converts a full-batch UserInsight (from InsightEngine.analyze_user_behavior)
        into a BehaviorProfileSnapshot.
        Accepts either a UserInsight Pydantic model or a plain dict.
        """
        if hasattr(insight, "dict"):
            data = insight.dict()
        elif isinstance(insight, dict):
            data = insight
        else:
            raise TypeError("insight must be a dict or a Pydantic model")

        top_cats = data.get("top_categories", [])
        if top_cats and hasattr(top_cats[0], "dict"):
            top_cats = [c.dict() if hasattr(c, "dict") else c for c in top_cats]

        return BehaviorProfileSnapshot(
            total_urls=data.get("total_urls_analyzed", 0),
            contributing_url_count=data.get("total_urls_analyzed", 0),
            is_stale=False,
            primary_interests=data.get("primary_interests", []),
            top_categories=[
                CategoryEntry(category=c.get("category", c.get("name", "Unknown")), score=c.get("score", 0.0))
                for c in top_cats
            ],
            productivity_rating=data.get("productivity_rating", 0.0),
            focus_score=data.get("focus_score", 0.0),
            time_wasting_probability=data.get("time_wasting_probability", 0.0),
            stress_indicators=data.get("stress_or_anxiety_indicators", 0.0),
            educational_alignment=data.get("educational_alignment", 0.0),
            academic_relevance=data.get("academic_relevance_score", 0.0),
            career_development=data.get("career_development_focus", 0.0),
            shopping_intent_score=data.get("shopping_intent_score", 0.0),
            likely_in_market_for=data.get("likely_in_market_for", []),
            overall_sentiment=data.get("overall_sentiment", "Unknown"),
            nsfw_probability=data.get("nsfw_or_inappropriate_probability", 0.0),
            risk_summary=data.get("risk_assessment_summary"),
            behavioral_summary=data.get("behavioral_summary", ""),
            actionable_recommendation=data.get("actionable_recommendation"),
            raw_ai_response=data.get("raw_ai_response", {}),
        )
