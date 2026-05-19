# Sitewise Crawler 🕷️🧠

[![Version](https://img.shields.io/pypi/v/sitewise-crawler)](https://pypi.org/project/sitewise-crawler/)
[![License](https://img.shields.io/github/license/tarxemo/sitewise-crawler)](https://github.com/tarxemo/sitewise-crawler/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/sitewise-crawler)](https://pypi.org/project/sitewise-crawler/)

**Sitewise Crawler** is an enterprise-grade Python library for browser-activity monitoring, behavioral intelligence, and automated risk reporting. It transforms raw URL streams into actionable psychological and productivity profiles.

---

## 📖 Table of Contents
1. [Installation](#-installation)
2. [Day 1: Integration Blueprint](#-day-1-integration-blueprint)
3. [Core Concepts & DTOs](#-core-concepts--dtos)
4. [Deep Dive: Modules](#-deep-dive-modules)
   - [InsightEngine (AI Analysis)](#insightengine-ai-analysis)
   - [SessionAnalyzer (Windowing)](#sessionanalyzer-windowing)
   - [AlertEngine (Custom Rules)](#alertengine-custom-rules)
5. [Academic & Institutional Value](#-academic--institutional-value)
6. [Configuration](#-configuration)

---

## 📦 Installation

```bash
# Core library
pip install sitewise-crawler

# Required for dynamic/SPA site support
playwright install chromium

# Optional: Required for PDF report generation
pip install reportlab
```

---

## 🚀 Day 1: Integration Blueprint

If you are a developer integrating this into a new application, here is the standard workflow:

### 1. The Environment
The library requires a **Groq API Key** for behavioral analysis.
```bash
export GROQ_API_KEY="your_api_key_here"
```

### 2. Basic Usage (The "Hello World" of Intelligence)
```python
import os
from sitewise_crawler import create_insight_engine, ProfileBlender, BehaviorProfileSnapshot

# 1. Initialize
engine = create_insight_engine(api_key=os.getenv("GROQ_API_KEY"))

# 2. Get a real-time risk assessment for a URL
risk_result = engine.quick_url_risk_sync("https://example.com")
print(f"Status: {risk_result['status']} | Category: {risk_result['category']}")

# 3. Blend into a user profile
# Start with an empty snapshot
profile = BehaviorProfileSnapshot(device_id="dev_001")
updated_profile = ProfileBlender.update_profile_from_risk(profile, risk_result)

print(f"New Productivity Score: {updated_profile.productivity_rating}")
```

---

## 🏗️ Core Concepts & DTOs

The library communicates via **Data Transfer Objects (DTOs)** implemented as Pydantic models. This ensures your backend and the library always speak the same language.

| Model | Description | Key Fields |
|---|---|---|
| `BehaviorProfileSnapshot` | The state of a user's behavior. | `productivity_rating`, `nsfw_probability`, `top_categories` |
| `URLRiskResult` | The output of a single URL check. | `status`, `risk_score`, `category`, `reason` |
| `SessionWindow` | A discrete block of browsing time. | `start_time`, `end_time`, `events`, `duration_seconds` |
| `Alert` | A fired security or productivity event. | `alert_type`, `severity`, `message`, `evidence` |

---

## 🧠 Deep Dive: Modules

### InsightEngine (AI Analysis)
The `InsightEngine` handles both fast-path (heuristic) and deep-path (LLM) analysis.
- **Fast Path**: Uses a built-in dictionary of millions of domains for instant classification.
- **Deep Path**: Crawls the page content, cleans it using `trafilatura`, and uses **Llama 3.3** to understand the intent.

### SessionAnalyzer (Windowing)
Transforms a continuous stream of logs into sessions.
- **Gap Detection**: Automatically starts a new session if the user is idle for > 30 minutes.
- **Aggregation**: Computes session-level stats (e.g., "Most distracting hour").

### AlertEngine (Custom Rules)
You can extend the alerting logic by adding your own rules.
```python
from sitewise_crawler import BaseAlertRule, Alert, Severity

class MyCustomRule(BaseAlertRule):
    def evaluate(self, ctx):
        if ctx.total_url_count_last_hour > 100:
            return Alert(
                alert_type="excessive_browsing",
                severity=Severity.MEDIUM,
                message="User is browsing at an extreme rate."
            )
        return None
```

---

## 🎓 Academic & Institutional Value

This library was built to satisfy high academic and institutional standards:
1.  **Explainability (XAI)**: Every score or alert includes an `evidence` object, allowing admins to see *why* the AI flagged a user.
2.  **Efficiency**: Uses **Exponential Moving Averages (EMA)** and **Trend Velocity**. Instead of re-calculating everything, it only processes the latest delta.
3.  **Privacy-First**: The library only extracts the "Semantic Core" of pages, ignoring personal identifying information in headers/sidebars.

---

## ⚙️ Configuration

The `CrawlerConfig` allows fine-grained control:

| Option | Default | Description |
|---|---|---|
| `use_playwright` | `False` | Set to `True` for JavaScript-heavy (SPA) sites. |
| `max_depth` | `3` | BFS depth for site discovery. |
| `timeout_ms` | `30000` | Network timeout per page. |
| `rate_limit_delay` | `1.0` | Seconds to wait between requests (politeness). |

---

## 🤝 Support & Contribution
This library is part of the **AegiVara** ecosystem. For bug reports or feature requests, please open an issue in the main repository.

---
**License**: MIT — Developed by **Group 8 FYP 2026**.
