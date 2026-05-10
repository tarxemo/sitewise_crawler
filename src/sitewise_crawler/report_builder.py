"""
report_builder.py
─────────────────
Structured report generation from AegiVara behavioral data.

This module is framework-agnostic.  It consumes plain Python data objects
(Pydantic models and dicts) and produces:

  • ``ReportSection``  — one labelled block of a report.
  • ``BehaviorReport`` — a fully assembled, serialisable report object.
  • ``ReportBuilder``  — factory that assembles reports from library types.
  • ``JSONReportExporter``  — serialises to a structured dict / JSON string.
  • ``TextReportExporter``  — produces a human-readable plain-text report.

PDF generation (optional) is available when ``reportlab`` is installed; the
module degrades gracefully to text export if the dependency is absent.

Usage from a Django view::

    from sitewise_crawler import ReportBuilder, JSONReportExporter
    from intelligence.models import DeviceBehaviorProfile

    profile = DeviceBehaviorProfile.objects.get(device=device)
    report  = ReportBuilder.from_behavior_profile(profile, device_name=device.device_name)
    payload = JSONReportExporter.export(report)
    return JsonResponse(payload)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# REPORT DATA MODELS
# ─────────────────────────────────────────────────────────────

class ReportSection(BaseModel):
    """One named section of a report, carrying arbitrary key-value pairs."""
    title: str
    data: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class BehaviorReport(BaseModel):
    """
    A fully assembled, serialisable behavioral report for a single device.

    This is the primary output of :class:`ReportBuilder`.
    """
    report_id: str
    device_id: str
    device_name: Optional[str] = None
    owner_id: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    report_period: Optional[str] = None   # e.g. "Last 7 days"
    sections: List[ReportSection] = Field(default_factory=list)

    # High-level summary fields (optional but useful for quick display)
    headline_summary: str = ""
    risk_level: str = "Low"              # Low | Medium | High | Critical
    actionable_recommendation: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# REPORT BUILDER
# ─────────────────────────────────────────────────────────────

class ReportBuilder:
    """
    Assembles a structured `BehaviorReport` from various telemetry sources.
    
    The ReportBuilder acts as a factory that transforms raw behavioral scores, 
    session summaries, and AI-generated insights into a hierarchical, 
    presentable document. It handles:
    
    1.  **Risk Level Computation**: Maps numerical risk scores to human-readable 
        levels (Critical, High, Medium, Low).
    2.  **Headline Synthesis**: Generates dynamic headings based on the 
        predominant behavior observed.
    3.  **Modular Section Assembly**: Constructing report segments for 
        Productivity, Safety, and Academic alignment.
    """

    @classmethod
    def from_behavior_profile(
        cls,
        profile: Any,
        device_name: Optional[str] = None,
        owner_id: Optional[str] = None,
        report_period: Optional[str] = "All time",
    ) -> BehaviorReport:
        """
        Build a report from a :class:`~sitewise_crawler.BehaviorProfileSnapshot`
        *or* any object/dict with matching attribute names (e.g. a Django ORM
        instance).

        Parameters
        ----------
        profile:
            A ``BehaviorProfileSnapshot``, Django ``DeviceBehaviorProfile``
            model instance, or plain dict.
        device_name:
            Human-readable name for the device.
        owner_id:
            Owner identifier (user PK, username, etc.).
        report_period:
            Human-readable label for the time range covered.
        """
        data = cls._to_dict(profile)
        device_id = str(data.get("device_id", data.get("device", "unknown")))
        report_id = f"report_{device_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        # ── Risk level ─────────────────────────────────────
        risk_level = cls._compute_risk_level(data)

        # ── Sections ───────────────────────────────────────
        sections = [
            cls._productivity_section(data),
            cls._content_section(data),
            cls._risk_section(data),
            cls._academic_section(data),
            cls._commercial_section(data),
        ]

        return BehaviorReport(
            report_id=report_id,
            device_id=device_id,
            device_name=device_name,
            owner_id=str(owner_id) if owner_id else None,
            report_period=report_period,
            sections=sections,
            headline_summary=data.get("behavioral_summary", "No summary available."),
            risk_level=risk_level,
            actionable_recommendation=data.get("actionable_recommendation"),
        )

    @classmethod
    def from_session_summary(
        cls,
        summary: Any,
        device_name: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> BehaviorReport:
        """
        Build a compact report from a ``SessionSummary``.
        """
        data = cls._to_dict(summary)
        device_id = str(data.get("device_id", "unknown"))
        report_id = f"session_report_{device_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        section = ReportSection(
            title="Session Statistics",
            data={
                "Total Sessions": data.get("total_sessions", 0),
                "Pages Visited": data.get("total_pages_visited", 0),
                "Unique Domains": data.get("total_unique_domains", 0),
                "Blocked Encounters": data.get("total_blocked_encounters", 0),
                "Suspicious Encounters": data.get("total_suspicious_encounters", 0),
                "Avg Session Duration (min)": data.get("avg_session_duration_minutes", 0.0),
                "Longest Session (min)": data.get("longest_session_minutes", 0.0),
                "Peak Activity Hour": data.get("peak_activity_hour", "N/A"),
                "Most Visited Domain": data.get("most_visited_domain", "N/A"),
                "Most Visited Category": data.get("most_visited_category", "N/A"),
            },
        )

        is_high_risk = data.get("is_high_risk", False)
        blocked = data.get("total_blocked_encounters", 0)

        return BehaviorReport(
            report_id=report_id,
            device_id=device_id,
            device_name=device_name,
            owner_id=str(owner_id) if owner_id else None,
            report_period="Recent Sessions",
            sections=[section],
            headline_summary=(
                f"{data.get('total_sessions', 0)} session(s) recorded. "
                f"{blocked} blocked URL encounter(s)."
            ),
            risk_level="High" if is_high_risk else "Low",
        )

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _to_dict(obj: Any) -> Dict[str, Any]:
        """Coerce object to dict — supports Pydantic models, Django ORM, dicts."""
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return {
                k: v for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }
        return {}

    @staticmethod
    def _compute_risk_level(data: Dict[str, Any]) -> str:
        nsfw = data.get("nsfw_probability", 0.0)
        blocked = data.get("blocked_url_count", 0) or data.get("total_blocked_encounters", 0)
        if nsfw > 0.7 or blocked > 10:
            return "Critical"
        if nsfw > 0.4 or blocked > 5:
            return "High"
        if nsfw > 0.2 or blocked > 2:
            return "Medium"
        return "Low"

    @staticmethod
    def _productivity_section(data: Dict[str, Any]) -> ReportSection:
        return ReportSection(
            title="Productivity & Focus",
            data={
                "Productivity Rating": f"{data.get('productivity_rating', 0.0):.0%}",
                "Focus Score": f"{data.get('focus_score', 0.0):.0%}",
                "Time-Wasting Probability": f"{data.get('time_wasting_probability', 0.0):.0%}",
                "Stress Indicators": f"{data.get('stress_indicators', 0.0):.0%}",
            },
        )

    @staticmethod
    def _content_section(data: Dict[str, Any]) -> ReportSection:
        return ReportSection(
            title="Content & Interests",
            data={
                "Primary Interests": data.get("primary_interests", []),
                "Top Categories": data.get("top_categories", []),
                "Overall Sentiment": data.get("overall_sentiment", "Unknown"),
                "Total URLs Analyzed": data.get("total_urls", data.get("total_urls_analyzed", 0)),
            },
        )

    @staticmethod
    def _risk_section(data: Dict[str, Any]) -> ReportSection:
        return ReportSection(
            title="Risk & Safety",
            data={
                "NSFW Probability": f"{data.get('nsfw_probability', 0.0):.0%}",
                "Risk Summary": data.get("risk_summary", "No risk data available."),
            },
            notes="Values above 35% are flagged as concerning.",
        )

    @staticmethod
    def _academic_section(data: Dict[str, Any]) -> ReportSection:
        return ReportSection(
            title="Academic & Career Alignment",
            data={
                "Educational Alignment": f"{data.get('educational_alignment', 0.0):.0%}",
                "Academic Relevance": f"{data.get('academic_relevance', 0.0):.0%}",
                "Career Development": f"{data.get('career_development', 0.0):.0%}",
            },
        )

    @staticmethod
    def _commercial_section(data: Dict[str, Any]) -> ReportSection:
        return ReportSection(
            title="Commercial Intent",
            data={
                "Shopping Intent Score": f"{data.get('shopping_intent_score', 0.0):.0%}",
                "Likely In Market For": data.get("likely_in_market_for", []),
            },
        )


# ─────────────────────────────────────────────────────────────
# EXPORTERS
# ─────────────────────────────────────────────────────────────

class JSONReportExporter:
    """Serialise a ``BehaviorReport`` to a dict or JSON string."""

    @staticmethod
    def export(report: BehaviorReport) -> Dict[str, Any]:
        """Return a plain dict (safe for Django's ``JsonResponse``)."""
        return report.model_dump(mode="json")

    @staticmethod
    def to_json_string(report: BehaviorReport, indent: int = 2) -> str:
        """Return a formatted JSON string."""
        return report.model_dump_json(indent=indent)


class TextReportExporter:
    """Produce a human-readable plain-text report."""

    @staticmethod
    def export(report: BehaviorReport) -> str:
        lines: List[str] = [
            "=" * 60,
            f"  AEGIVARA BEHAVIORAL REPORT",
            f"  Device : {report.device_name or report.device_id}",
            f"  Period : {report.report_period or 'N/A'}",
            f"  Generated : {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"  Risk Level : {report.risk_level}",
            "=" * 60,
            "",
            f"SUMMARY",
            "-" * 40,
            report.headline_summary,
            "",
        ]

        for section in report.sections:
            lines.append(f"{section.title.upper()}")
            lines.append("-" * 40)
            for key, value in section.data.items():
                if isinstance(value, list):
                    value_str = ", ".join(str(v) for v in value) if value else "None"
                else:
                    value_str = str(value)
                lines.append(f"  {key:<35} {value_str}")
            if section.notes:
                lines.append(f"  NOTE: {section.notes}")
            lines.append("")

        if report.actionable_recommendation:
            lines += [
                "RECOMMENDATION",
                "-" * 40,
                report.actionable_recommendation,
                "",
            ]

        lines.append("=" * 60)
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# OPTIONAL: PDF EXPORT (requires reportlab)
# ─────────────────────────────────────────────────────────────

class PDFReportExporter:
    """
    Exports a ``BehaviorReport`` to a PDF byte stream.

    Requires the ``reportlab`` package::

        pip install reportlab

    If ``reportlab`` is not installed this class raises ``ImportError`` only
    when ``export()`` is called — so it is safe to import unconditionally.
    """

    @staticmethod
    def export(report: BehaviorReport) -> bytes:
        """
        Returns raw PDF bytes that can be served via Django's
        ``HttpResponse(content_type='application/pdf')``.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
            )
            from reportlab.lib import colors
            import io
        except ImportError as exc:
            raise ImportError(
                "PDFReportExporter requires 'reportlab'. "
                "Install it with: pip install reportlab"
            ) from exc

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        # ── Title ───────────────────────────────────────────
        story.append(Paragraph("AegiVara Behavioral Report", styles["Title"]))
        story.append(Spacer(1, 0.3*cm))
        meta_data = [
            ["Device", report.device_name or report.device_id],
            ["Period", report.report_period or "N/A"],
            ["Generated", report.generated_at.strftime("%Y-%m-%d %H:%M UTC")],
            ["Risk Level", report.risk_level],
        ]
        meta_table = Table(meta_data, colWidths=[4*cm, 12*cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.5*cm))

        # ── Summary ──────────────────────────────────────────
        story.append(Paragraph("Summary", styles["Heading2"]))
        story.append(Paragraph(report.headline_summary, styles["BodyText"]))
        story.append(Spacer(1, 0.4*cm))

        # ── Sections ──────────────────────────────────────────
        for section in report.sections:
            story.append(Paragraph(section.title, styles["Heading3"]))
            rows = []
            for key, value in section.data.items():
                if isinstance(value, list):
                    val_str = ", ".join(str(v) for v in value) if value else "None"
                else:
                    val_str = str(value)
                rows.append([key, val_str])
            if rows:
                tbl = Table(rows, colWidths=[7*cm, 9*cm])
                tbl.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(tbl)
            if section.notes:
                story.append(Paragraph(f"Note: {section.notes}", styles["Italic"]))
            story.append(Spacer(1, 0.4*cm))

        # ── Recommendation ────────────────────────────────────
        if report.actionable_recommendation:
            story.append(Paragraph("Recommendation", styles["Heading3"]))
            story.append(Paragraph(report.actionable_recommendation, styles["BodyText"]))

        doc.build(story)
        return buffer.getvalue()
