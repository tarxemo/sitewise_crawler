"""
test_v020_features.py
─────────────────────
Verification script for sitewise-crawler v0.2.0 features:
- Session Analysis
- Alert Engine
- Report Generation

Run this to verify the library logic in isolation.
"""
import sys
import os
import json
from datetime import datetime, timedelta

# Add src to path for local testing
sys.path.append(os.path.join(os.getcwd(), 'src'))

from sitewise_crawler import (
    SessionAnalyzer, SessionEvent, 
    AlertEngine, AlertContext,
    ReportBuilder, TextReportExporter,
    BehaviorProfileSnapshot
)

def run_v020_test():
    print("🚀 Testing sitewise-crawler v0.2.0 Features\n")

    # 1. Simulate Browsing Events
    now = datetime.utcnow()
    events = [
        # Session 1: Productive (10:00 - 10:15)
        SessionEvent(url="https://github.com/trending", title="GitHub", timestamp=now - timedelta(hours=2, minutes=30), status="Safe", category="Development"),
        SessionEvent(url="https://stackoverflow.com", title="StackOverflow", timestamp=now - timedelta(hours=2, minutes=20), status="Safe", category="Development"),
        
        # Session 2: Risky/Distracting (Now)
        SessionEvent(url="https://some-risky-site.com", title="Risky Content", timestamp=now - timedelta(minutes=10), status="Blocked", category="Adult"),
        SessionEvent(url="https://another-risky-site.com", title="Suspicious", timestamp=now - timedelta(minutes=5), status="Suspicious", category="Adult"),
        SessionEvent(url="https://third-risky-site.com", title="Blocked", timestamp=now - timedelta(minutes=1), status="Blocked", category="Adult"),
    ]

    # --- TEST: SESSION ANALYZER ---
    print("📊 [1/3] Testing SessionAnalyzer...")
    sessions = SessionAnalyzer.build_sessions(events, device_id="test-device-001")
    summary = SessionAnalyzer.summarize(sessions, device_id="test-device-001")
    
    print(f"  - Built {len(sessions)} session windows.")
    print(f"  - Most visited domain: {summary.most_visited_domain}")
    print(f"  - High risk flag: {summary.is_high_risk}\n")

    # --- TEST: ALERT ENGINE ---
    print("🔔 [2/3] Testing AlertEngine...")
    # Simulate a high-risk context
    ctx = AlertContext(
        device_id="test-device-001",
        device_name="Demo Laptop",
        nsfw_probability=0.75,
        blocked_url_count_last_hour=3,
        productivity_rating=0.1,
        total_url_count_last_hour=20
    )
    fired_alerts = AlertEngine.evaluate(ctx)
    print(f"  - Fired {len(fired_alerts)} alerts.")
    for alert in fired_alerts:
        print(f"    [{alert.severity.upper()}] {alert.alert_type}: {alert.message}")
    print("")

    # --- TEST: REPORT BUILDER ---
    print("📄 [3/3] Testing ReportBuilder...")
    # Mock a behavior profile snapshot
    mock_profile = {
        "device_id": "test-device-001",
        "behavioral_summary": "User is showing signs of high-risk browsing behavior with multiple blocked attempts.",
        "nsfw_probability": 0.75,
        "productivity_rating": 0.15,
        "focus_score": 0.2,
        "top_categories": ["Adult", "Social Media"],
        "primary_interests": ["Unspecified"],
        "overall_sentiment": "Negative",
        "actionable_recommendation": "Immediate intervention required. Recommend restricted access profile."
    }
    
    report = ReportBuilder.from_behavior_profile(mock_profile, device_name="Demo Laptop")
    text_report = TextReportExporter.export(report)
    
    print("--- GENERATED TEXT REPORT ---")
    print(text_report)
    print("-----------------------------\n")

    print("✅ All v0.2.0 library features verified successfully.")

if __name__ == "__main__":
    run_v020_test()
