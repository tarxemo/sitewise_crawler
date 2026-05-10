"""
session_analyzer.py
───────────────────
Pure-Python session analysis engine.

A "session" in AegiVara is a contiguous sequence of URL visits from a single
device within a rolling time window.  This module provides:

  • SessionEvent        — lightweight DTO for a single URL visit event
  • SessionWindow       — groups events into a logical browsing session
  • SessionAnalyzer     — stateless engine that ingests raw URL log data and
                          produces rich session-level statistics that the backend
                          (or any other consumer) can persist / query.

All types are Pydantic models so callers can serialise / validate freely.
No Django, Flask, or any web-framework dependency is introduced here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# DATA TRANSFER OBJECTS
# ─────────────────────────────────────────────────────────────

class SessionEvent(BaseModel):
    """
    Represents a single URL-visit event captured by the browser extension.
    Mirrors the URLLog Django model but is framework-agnostic.
    """
    url: str
    title: Optional[str] = None
    timestamp: datetime
    status: str = "Safe"  # Safe | Suspicious | Blocked
    category: Optional[str] = None  # Filled in by DomainClassifier if available


class SessionWindow(BaseModel):
    """
    A contiguous block of browsing activity grouped into a logical session.
    """
    session_id: str
    device_id: str
    start_time: datetime
    end_time: datetime
    events: List[SessionEvent] = Field(default_factory=list)

    # ── Computed properties ──────────────────────────────────

    @property
    def duration_minutes(self) -> float:
        delta = self.end_time - self.start_time
        return round(delta.total_seconds() / 60, 2)

    @property
    def total_pages(self) -> int:
        return len(self.events)

    @property
    def unique_domains(self) -> int:
        from urllib.parse import urlparse
        return len({urlparse(e.url).netloc for e in self.events})

    @property
    def blocked_count(self) -> int:
        return sum(1 for e in self.events if e.status == "Blocked")

    @property
    def suspicious_count(self) -> int:
        return sum(1 for e in self.events if e.status == "Suspicious")


class SessionSummary(BaseModel):
    """
    Aggregated statistics for a set of session windows belonging to one device.
    """
    device_id: str
    total_sessions: int = 0
    total_pages_visited: int = 0
    total_unique_domains: int = 0
    total_blocked_encounters: int = 0
    total_suspicious_encounters: int = 0

    avg_session_duration_minutes: float = 0.0
    longest_session_minutes: float = 0.0
    shortest_session_minutes: float = 0.0

    peak_activity_hour: Optional[int] = None        # 0-23
    most_visited_domain: Optional[str] = None
    most_visited_category: Optional[str] = None

    # Sessions ordered newest-first
    recent_sessions: List[SessionWindow] = Field(default_factory=list)

    # Derived risk flag
    is_high_risk: bool = False


# ─────────────────────────────────────────────────────────────
# ANALYZER ENGINE
# ─────────────────────────────────────────────────────────────

class SessionAnalyzer:
    """
    Stateless engine that transforms raw URL-log data into structured session
    windows and aggregated summaries.
    
    Session analysis is the process of partitioning a continuous stream of 
    browsing events into discrete temporal blocks. This allows for the 
    calculation of session-specific metrics such as average duration, peak 
    usage times, and engagement depth.
    
    The engine uses a "Sliding Gap" algorithm: if the time delta between two 
    sequential events exceeds a predefined threshold (e.g., 30 minutes), 
    the current session is finalized and a new window is initialized.
    """

    # Two events more than GAP_MINUTES apart belong to different sessions.
    DEFAULT_GAP_MINUTES: int = 30

    # ── Session building ─────────────────────────────────────

    @classmethod
    def build_sessions(
        cls,
        events: List[SessionEvent],
        device_id: str = "unknown",
        gap_minutes: int = DEFAULT_GAP_MINUTES,
    ) -> List[SessionWindow]:
        """
        Partition a time-ordered sequence of events into discrete sessions.
        
        This algorithm identifies contiguous blocks of activity where the 
        idle time between visits does not exceed the `gap_minutes` threshold.
        
        Args:
            events: Chronologically sorted list of `SessionEvent` objects.
            device_id: Identifier for the originating device.
            gap_minutes: Idle time threshold for session termination.
            
        Returns:
            A list of `SessionWindow` objects, each containing its component events.
        """
        if not events:
            return []

        sorted_events = sorted(events, key=lambda e: e.timestamp)
        sessions: List[SessionWindow] = []
        gap = timedelta(minutes=gap_minutes)

        current_events: List[SessionEvent] = [sorted_events[0]]

        for event in sorted_events[1:]:
            if event.timestamp - current_events[-1].timestamp > gap:
                # Close current session and open a new one
                sessions.append(cls._make_window(current_events, device_id, len(sessions)))
                current_events = []
            current_events.append(event)

        # Flush last batch
        if current_events:
            sessions.append(cls._make_window(current_events, device_id, len(sessions)))

        logger.info(
            f"[SessionAnalyzer] Built {len(sessions)} session(s) "
            f"from {len(events)} event(s) for device {device_id!r}."
        )
        return sessions

    @staticmethod
    def _make_window(
        events: List[SessionEvent],
        device_id: str,
        index: int,
    ) -> SessionWindow:
        """Internal helper — constructs a SessionWindow from an event batch."""
        return SessionWindow(
            session_id=f"{device_id}_s{index}",
            device_id=device_id,
            start_time=events[0].timestamp,
            end_time=events[-1].timestamp,
            events=events,
        )

    # ── Summary ──────────────────────────────────────────────

    @classmethod
    def summarize(
        cls,
        sessions: List[SessionWindow],
        device_id: str = "unknown",
        recent_limit: int = 5,
    ) -> SessionSummary:
        """
        Compute aggregate statistics across all session windows for a device.

        Parameters
        ----------
        sessions:
            Output of :meth:`build_sessions`.
        device_id:
            Propagated into the summary.
        recent_limit:
            How many of the most recent sessions to include in
            ``summary.recent_sessions``.

        Returns
        -------
        SessionSummary
        """
        if not sessions:
            return SessionSummary(device_id=device_id)

        durations = [s.duration_minutes for s in sessions]
        all_events = [e for s in sessions for e in s.events]

        domain_counts = cls._count_domains(all_events)
        category_counts = cls._count_categories(all_events)
        peak_hour = cls._peak_activity_hour(all_events)

        total_blocked = sum(s.blocked_count for s in sessions)
        is_high_risk = total_blocked > 5 or (
            total_blocked / max(len(all_events), 1) > 0.15
        )

        return SessionSummary(
            device_id=device_id,
            total_sessions=len(sessions),
            total_pages_visited=sum(s.total_pages for s in sessions),
            total_unique_domains=len(domain_counts),
            total_blocked_encounters=total_blocked,
            total_suspicious_encounters=sum(s.suspicious_count for s in sessions),
            avg_session_duration_minutes=round(sum(durations) / len(durations), 2),
            longest_session_minutes=max(durations),
            shortest_session_minutes=min(durations),
            peak_activity_hour=peak_hour,
            most_visited_domain=max(domain_counts, key=domain_counts.get) if domain_counts else None,
            most_visited_category=max(category_counts, key=category_counts.get) if category_counts else None,
            recent_sessions=sorted(sessions, key=lambda s: s.start_time, reverse=True)[:recent_limit],
            is_high_risk=is_high_risk,
        )

    # ── Private helpers ──────────────────────────────────────

    @staticmethod
    def _count_domains(events: List[SessionEvent]) -> Dict[str, int]:
        from urllib.parse import urlparse
        counts: Dict[str, int] = {}
        for e in events:
            try:
                domain = urlparse(e.url).netloc.lower().replace("www.", "")
                if domain:
                    counts[domain] = counts.get(domain, 0) + 1
            except Exception:
                continue
        return counts

    @staticmethod
    def _count_categories(events: List[SessionEvent]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in events:
            if e.category:
                counts[e.category] = counts.get(e.category, 0) + 1
        return counts

    @staticmethod
    def _peak_activity_hour(events: List[SessionEvent]) -> Optional[int]:
        hour_counts: Dict[int, int] = {}
        for e in events:
            h = e.timestamp.hour
            hour_counts[h] = hour_counts.get(h, 0) + 1
        return max(hour_counts, key=hour_counts.get) if hour_counts else None
