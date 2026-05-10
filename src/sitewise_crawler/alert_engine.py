"""
alert_engine.py
───────────────
Threshold-based, rule-driven alerting for the AegiVara monitoring platform.

This module is **100 % framework-agnostic** — it contains no Django, Flask, or
database code.  The backend (or any consumer) is responsible for:

  1. Building ``AlertContext`` objects from its own data stores.
  2. Calling ``AlertEngine.evaluate(ctx)`` to receive a list of fired
     ``Alert`` objects.
  3. Persisting / dispatching those alerts however it sees fit.

Built-in rule sets
------------------
  • ``NSFWAlert``             — NSFW probability above threshold.
  • ``HighRiskSessionAlert``  — Too many blocked URLs in a session.
  • ``LowProductivityAlert``  — Sustained low productivity score.
  • ``SuddenSpikeAlert``      — Unusual jump in pages-per-minute.
  • ``OffHoursAlert``         — Active browsing outside allowed hours.

Custom rules can be added by subclassing ``BaseAlertRule``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# SEVERITY ENUM
# ─────────────────────────────────────────────────────────────

class Severity:
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


# ─────────────────────────────────────────────────────────────
# ALERT MODEL  — returned by every rule when it fires
# ─────────────────────────────────────────────────────────────

class Alert(BaseModel):
    """
    A fired alert — backend-agnostic DTO.

    The backend should persist these into its own ``Alert`` or
    ``Notification`` model.
    """
    alert_type: str
    severity: str
    device_id: str
    device_name: Optional[str] = None
    owner_id: Optional[str] = None
    message: str
    detail: str = ""
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    evidence: Dict[str, Any] = Field(default_factory=dict)

    # Whether the alert should push an immediate notification (e.g. email/SMS)
    requires_immediate_action: bool = False


# ─────────────────────────────────────────────────────────────
# ALERT CONTEXT  — all data an alert rule may need to inspect
# ─────────────────────────────────────────────────────────────

class AlertContext(BaseModel):
    """
    Snapshot of a device's current state passed to all alert rules.

    The backend populates this from its ORM models; the alert engine is only
    ever given this plain Pydantic object.
    """
    device_id: str
    device_name: Optional[str] = None
    owner_id: Optional[str] = None

    # ── Behavioral profile scores (from DeviceBehaviorProfile) ──
    nsfw_probability: float = 0.0
    productivity_rating: float = 1.0
    time_wasting_probability: float = 0.0
    focus_score: float = 1.0
    stress_indicators: float = 0.0

    # ── Recent activity counters ──────────────────────────────
    blocked_url_count_last_hour: int = 0
    suspicious_url_count_last_hour: int = 0
    total_url_count_last_hour: int = 0
    pages_per_minute_current: float = 0.0

    # ── Session timing ────────────────────────────────────────
    current_hour: int = Field(default_factory=lambda: datetime.utcnow().hour)

    # ── Policy context ────────────────────────────────────────
    allowed_hours: Optional[tuple] = None  # e.g. (8, 22) → 8 am – 10 pm

    # ── Contextual flags ──────────────────────────────────────
    is_student_device: bool = False
    last_known_category: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# BASE RULE INTERFACE
# ─────────────────────────────────────────────────────────────

class BaseAlertRule(ABC):
    """
    Abstract base class for all alert rules.

    Subclass this and implement ``evaluate`` to add custom rules.
    """

    @abstractmethod
    def evaluate(self, ctx: AlertContext) -> Optional[Alert]:
        """
        Inspect the context and return an ``Alert`` if the rule fires,
        or ``None`` if conditions are not met.
        """
        ...


# ─────────────────────────────────────────────────────────────
# BUILT-IN RULES
# ─────────────────────────────────────────────────────────────

class NSFWAlertRule(BaseAlertRule):
    """Fires when the device's NSFW probability exceeds the threshold."""

    def __init__(self, threshold: float = 0.35):
        self.threshold = threshold

    def evaluate(self, ctx: AlertContext) -> Optional[Alert]:
        if ctx.nsfw_probability < self.threshold:
            return None
        severity = Severity.CRITICAL if ctx.nsfw_probability > 0.7 else Severity.HIGH
        return Alert(
            alert_type="nsfw_content_detected",
            severity=severity,
            device_id=ctx.device_id,
            device_name=ctx.device_name,
            owner_id=ctx.owner_id,
            message=f"Inappropriate content detected on '{ctx.device_name or ctx.device_id}'.",
            detail=(
                f"NSFW probability is {ctx.nsfw_probability:.0%}, "
                f"exceeding the {self.threshold:.0%} threshold."
            ),
            evidence={"nsfw_probability": ctx.nsfw_probability, "threshold": self.threshold},
            requires_immediate_action=ctx.nsfw_probability > 0.7,
        )


class HighRiskSessionAlertRule(BaseAlertRule):
    """Fires when too many blocked URLs are encountered within the last hour."""

    def __init__(self, max_blocked: int = 3):
        self.max_blocked = max_blocked

    def evaluate(self, ctx: AlertContext) -> Optional[Alert]:
        if ctx.blocked_url_count_last_hour <= self.max_blocked:
            return None
        return Alert(
            alert_type="high_risk_session",
            severity=Severity.HIGH,
            device_id=ctx.device_id,
            device_name=ctx.device_name,
            owner_id=ctx.owner_id,
            message=f"High-risk browsing session on '{ctx.device_name or ctx.device_id}'.",
            detail=(
                f"{ctx.blocked_url_count_last_hour} blocked URLs in the last hour "
                f"(threshold: {self.max_blocked})."
            ),
            evidence={
                "blocked_last_hour": ctx.blocked_url_count_last_hour,
                "threshold": self.max_blocked,
            },
            requires_immediate_action=True,
        )


class LowProductivityAlertRule(BaseAlertRule):
    """Fires when sustained productivity drops below the threshold."""

    def __init__(self, min_productivity: float = 0.25, min_urls: int = 10):
        self.min_productivity = min_productivity
        self.min_urls = min_urls

    def evaluate(self, ctx: AlertContext) -> Optional[Alert]:
        if ctx.total_url_count_last_hour < self.min_urls:
            return None  # Not enough data yet
        if ctx.productivity_rating >= self.min_productivity:
            return None
        return Alert(
            alert_type="low_productivity",
            severity=Severity.MEDIUM,
            device_id=ctx.device_id,
            device_name=ctx.device_name,
            owner_id=ctx.owner_id,
            message=f"Low productivity detected on '{ctx.device_name or ctx.device_id}'.",
            detail=(
                f"Productivity rating is {ctx.productivity_rating:.0%} "
                f"(minimum expected: {self.min_productivity:.0%})."
            ),
            evidence={
                "productivity_rating": ctx.productivity_rating,
                "time_wasting_probability": ctx.time_wasting_probability,
                "threshold": self.min_productivity,
            },
        )


class SuddenSpikeAlertRule(BaseAlertRule):
    """Fires when pages-per-minute is unusually high (possible bot/scraper)."""

    def __init__(self, max_pages_per_minute: float = 10.0):
        self.max_pages_per_minute = max_pages_per_minute

    def evaluate(self, ctx: AlertContext) -> Optional[Alert]:
        if ctx.pages_per_minute_current <= self.max_pages_per_minute:
            return None
        return Alert(
            alert_type="unusual_browsing_speed",
            severity=Severity.MEDIUM,
            device_id=ctx.device_id,
            device_name=ctx.device_name,
            owner_id=ctx.owner_id,
            message=f"Unusually rapid browsing on '{ctx.device_name or ctx.device_id}'.",
            detail=(
                f"Current pace: {ctx.pages_per_minute_current:.1f} pages/min "
                f"(threshold: {self.max_pages_per_minute:.1f})."
            ),
            evidence={
                "pages_per_minute": ctx.pages_per_minute_current,
                "threshold": self.max_pages_per_minute,
            },
        )


class OffHoursAlertRule(BaseAlertRule):
    """
    Fires when browsing occurs outside allowed hours.
    Only applies when ``ctx.allowed_hours`` is set AND ``ctx.is_student_device``
    is True (institution-specific rule).
    """

    def evaluate(self, ctx: AlertContext) -> Optional[Alert]:
        if not ctx.is_student_device or ctx.allowed_hours is None:
            return None
        start_h, end_h = ctx.allowed_hours
        if start_h <= ctx.current_hour < end_h:
            return None  # Within allowed window
        return Alert(
            alert_type="off_hours_activity",
            severity=Severity.LOW,
            device_id=ctx.device_id,
            device_name=ctx.device_name,
            owner_id=ctx.owner_id,
            message=f"Off-hours activity detected on '{ctx.device_name or ctx.device_id}'.",
            detail=(
                f"Active at hour {ctx.current_hour:02d}:00 UTC; "
                f"allowed window is {start_h:02d}:00–{end_h:02d}:00."
            ),
            evidence={
                "current_hour": ctx.current_hour,
                "allowed_hours": ctx.allowed_hours,
            },
        )


# ─────────────────────────────────────────────────────────────
# ALERT ENGINE  — evaluates all rules and returns fired alerts
# ─────────────────────────────────────────────────────────────

class AlertEngine:
    """
    Stateless engine that evaluates a set of alert rules against a context.
    
    The AlertEngine serves as the centralized policy enforcement layer. It 
    decouples the detection logic (rules) from the system state (context), 
    allowing for dynamic and extensible monitoring.
    
    Processing Flow:
    1.  **Context Injection**: Ingests a snapshot of current device metrics.
    2.  **Rule Execution**: Iterates through a collection of `BaseAlertRule` 
        instances, each responsible for a specific behavioral anomaly.
    3.  **Synthesis**: Aggregates fired alerts, sorts them by severity, and 
        flags any critical actions required.
    """

    # Default rule set — callers can pass custom rules to evaluate()
    DEFAULT_RULES: List[BaseAlertRule] = [
        NSFWAlertRule(),
        HighRiskSessionAlertRule(),
        LowProductivityAlertRule(),
        SuddenSpikeAlertRule(),
        OffHoursAlertRule(),
    ]

    @classmethod
    def evaluate(
        cls,
        ctx: AlertContext,
        rules: Optional[List[BaseAlertRule]] = None,
    ) -> List[Alert]:
        """
        Run all rules against the context.

        Parameters
        ----------
        ctx:
            Device state snapshot.
        rules:
            Override the default rule set.  Pass an empty list to evaluate no
            rules (useful in tests).

        Returns
        -------
        list[Alert]
            Only the alerts that fired (i.e. rules whose ``evaluate`` returned
            non-None), ordered by severity (critical → low).
        """
        active_rules = rules if rules is not None else cls.DEFAULT_RULES
        fired: List[Alert] = []

        for rule in active_rules:
            try:
                alert = rule.evaluate(ctx)
                if alert is not None:
                    fired.append(alert)
            except Exception as exc:
                logger.error(
                    f"[AlertEngine] Rule {rule.__class__.__name__} raised: {exc}"
                )

        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        fired.sort(key=lambda a: severity_order.get(a.severity, 99))

        if fired:
            logger.info(
                f"[AlertEngine] {len(fired)} alert(s) fired for device "
                f"{ctx.device_id!r}: "
                f"{[a.alert_type for a in fired]}"
            )
        return fired

    @classmethod
    def has_critical(cls, alerts: List[Alert]) -> bool:
        """Convenience — True if any alert is critical severity."""
        return any(a.severity == Severity.CRITICAL for a in alerts)

    @classmethod
    def requires_immediate_action(cls, alerts: List[Alert]) -> bool:
        """Convenience — True if at least one alert requires immediate action."""
        return any(a.requires_immediate_action for a in alerts)
