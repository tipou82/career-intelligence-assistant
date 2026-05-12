"""Markdown report generator — produces reports/weekly_career_brief_YYYY-WW.md."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .database import get_all_articles, get_articles_for_week, init_db, save_report

CONFIG_DIR = Path(__file__).parent.parent / "config"
REPORTS_DIR = Path(__file__).parent.parent / "reports"


# ---------------------------------------------------------------------------
# Week helpers
# ---------------------------------------------------------------------------

def get_week_label(reference: Optional[str] = None) -> str:
    """Return an ISO week label 'YYYY-WW'.

    reference='current' or None → this week
    reference='last'           → previous week
    reference='YYYY-WW'        → passed through unchanged
    """
    if reference in (None, "current"):
        d = date.today()
    elif reference == "last":
        d = date.today() - timedelta(weeks=1)
    else:
        return reference
    year, week, _ = d.isocalendar()
    return f"{year}-{week:02d}"


# ---------------------------------------------------------------------------
# Helpers for classification JSON
# ---------------------------------------------------------------------------

def _get_classification(article: Dict) -> Dict:
    raw = article.get("classification")
    if raw:
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Signal filtering
# ---------------------------------------------------------------------------

def _build_strong_signals(articles: List[Dict]) -> List[Dict]:
    return [
        a for a in articles
        if a.get("signal_strength") == "strong"
    ]


def _build_weak_signals(articles: List[Dict]) -> List[Dict]:
    return [
        a for a in articles
        if a.get("signal_strength") == "weak" and a.get("relevance_score", 0) >= 4.5
    ]


# ---------------------------------------------------------------------------
# Section formatters
# ---------------------------------------------------------------------------

def _format_signal_entry(article: Dict) -> str:
    cls = _get_classification(article)
    score = article.get("relevance_score", 0)
    title = article.get("title", "Untitled")
    summary = (article.get("summary") or "")[:350].strip()
    companies = ", ".join(cls.get("companies", [])) or "N/A"
    regions = ", ".join(cls.get("regions", [])) or "N/A"
    industries = ", ".join(cls.get("industries", [])) or "N/A"
    techs = ", ".join(cls.get("technologies", [])) or "N/A"
    skills = ", ".join(cls.get("skills", [])) or "your profile"
    confidence = article.get("confidence_level", "low")
    action = article.get("recommended_action", "watch")
    source = article.get("source_name", "Unknown")
    pub_date = str(article.get("published_date", ""))[:10]

    lines = [
        f"### {title}",
        f"- **Development:** {summary}",
        f"- **Companies involved:** {companies}",
        f"- **Region:** {regions}",
        f"- **Industry domain:** {industries}",
        f"- **Technology signal:** {techs}",
        f"- **Career relevance:** Directly relevant to {skills}",
        f"- **Confidence level:** {confidence}",
        f"- **Relevance score:** {score:.1f} / 10",
        f"- **Recommended action:** {action}",
        f"- **Source:** {source} — {pub_date}",
    ]
    url = article.get("url", "")
    if url:
        lines.append(f"- **URL:** {url}")
    return "\n".join(lines)


def _build_skill_table(strong_signals: List[Dict], skill_matrix: Dict) -> str:
    tech_counts: Dict[str, int] = {}
    for article in strong_signals:
        cls = _get_classification(article)
        for item in cls.get("technologies", []) + cls.get("skills", []):
            tech_counts[item.lower()] = tech_counts.get(item.lower(), 0) + 1

    rows: List[str] = []
    for skill in skill_matrix.get("skills", []):
        name = skill["name"]
        priority = skill.get("priority", "medium")
        effort = f"{skill.get('weekly_hours', 1)} h"
        triggers = [t.lower() for t in skill.get("triggers", {}).get("increase", [])]
        triggered = [t for t in triggers if t in tech_counts]
        if triggered:
            change = "↑"
            reason = f"Signals: {', '.join(triggered[:3])}"
        else:
            change = "→"
            reason = "No new signals this week"
        rows.append(f"| {name} | {priority} | {change} | {reason} | {effort} |")

    header = "| Skill | Current Priority | Change | Reason | Recommended Weekly Effort |"
    separator = "|---|---|---|---|---|"
    return "\n".join([header, separator] + rows)


def _build_learning_plan(skill_matrix: Dict) -> str:
    lines: List[str] = []
    total = 0
    for skill in skill_matrix.get("skills", []):
        hours = skill.get("weekly_hours", 1)
        task = skill.get("learning_task", skill["name"])
        lines.append(f"- **{hours} h:** {task}")
        total += hours
    lines.append(f"\n_Total: ~{total} hours_")
    return "\n".join(lines)


def _build_source_list(articles: List[Dict]) -> str:
    lines: List[str] = []
    seen: set = set()
    for a in sorted(articles, key=lambda x: x.get("relevance_score", 0), reverse=True):
        url = a.get("url", "")
        if url in seen:
            continue
        seen.add(url)
        date_str = str(a.get("published_date", ""))[:10]
        source = a.get("source_name", "Unknown")
        title = a.get("title", "Untitled")
        if url:
            lines.append(f"- [{title}]({url}) — {source} ({date_str})")
        else:
            lines.append(f"- {title} — {source} ({date_str})")
    return "\n".join(lines) if lines else "_No sources collected this week._"


def _build_executive_summary(
    strong: List[Dict], weak: List[Dict], week: str
) -> str:
    if not strong:
        return (
            f"Week {week} produced **no strong signals**. "
            f"{len(weak)} weak signal(s) are listed for monitoring. "
            "Existing skill priorities remain valid — no changes recommended."
        )
    industries: set = set()
    companies: set = set()
    for a in strong:
        cls = _get_classification(a)
        industries.update(cls.get("industries", []))
        companies.update(cls.get("companies", []))
    ind_str = ", ".join(list(industries)[:5]) or "multiple domains"
    co_str = ", ".join(list(companies)[:5]) or "various companies"
    return (
        f"Week {week} produced **{len(strong)} strong signal(s)** and "
        f"**{len(weak)} weak signal(s)**. "
        f"Key activity in: {ind_str}. Notable companies: {co_str}. "
        "See Section 2 for full analysis."
    )


def _build_career_advice(strong_signals: List[Dict]) -> str:
    if not strong_signals:
        return (
            "No major shifts this week. Continue current priorities: ROS2 implementation, "
            "C++20 safety logic, AI perception monitoring, and fault injection tests.\n\n"
            "Your portfolio project (Safety-Supervised Edge AI Demo on Raspberry Pi) "
            "remains well-aligned with the industry direction in embedded AI safety."
        )
    industries: set = set()
    techs: set = set()
    for a in strong_signals:
        cls = _get_classification(a)
        industries.update(i.lower() for i in cls.get("industries", []))
        techs.update(t.lower() for t in cls.get("technologies", []))

    parts = [
        "Based on this week's signals, your positioning in "
        "**functional safety + embedded AI systems** remains strategically sound.\n"
    ]
    if "robotics" in industries or "humanoid" in techs or "physical ai" in techs:
        parts.append(
            "**Robotics activity is strong.** Emphasize ROS2 and safety-supervised "
            "robotics in your portfolio and CV/LinkedIn profile.\n"
        )
    if "sotif" in techs or "iso/pas 8800" in techs:
        parts.append(
            "**SOTIF/ISO PAS 8800 signals are visible.** This reinforces your AI safety "
            "specialization. Highlight it when applying to ADAS-focused or AI-safety roles.\n"
        )
    if "mbse" in techs or "sysml" in techs:
        parts.append(
            "**MBSE/SysML2 signals detected.** Consider adding SysML2 architecture "
            "diagrams to your portfolio project to demonstrate systems engineering depth.\n"
        )
    if "qnx" in techs or "software_defined_vehicle" in industries:
        parts.append(
            "**SDV / QNX signals present.** Your QNX/POSIX supervisor knowledge "
            "is a differentiator for automotive SDV roles — make it visible.\n"
        )
    if not parts[1:]:
        parts.append(
            "Signals this week are broad. No specific pivot recommended. "
            "Maintain current skill trajectory.\n"
        )
    return "\n".join(parts)


def _build_risks_section(noise_articles: List[Dict]) -> str:
    warnings = [
        "- **Generic GenAI / chatbot news:** Not relevant unless tied to "
        "safety-critical or embedded systems.",
        "- **Single-startup hype without hiring or technical signal:** "
        "Log it, but do not change skill priorities.",
        "- **Vague 'AI transformation' press releases:** Low signal density; "
        "treat as background noise.",
        "- **Consumer robotics without safety or embedded angle:** "
        "Watch passively; do not deprioritize core skills.",
        "- **Social media opinion pieces without corroborating sources:** "
        "Low confidence; require a second source before acting.",
    ]
    if noise_articles:
        titles = "\n".join(f"  - {a['title'][:90]}" for a in noise_articles[:6])
        warnings.append(f"- **Low-relevance articles filtered this week:**\n{titles}")
    return "\n".join(warnings)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_report(week_label: Optional[str] = None) -> Path:
    """Generate and save the weekly Markdown report. Returns the report file path."""
    init_db()
    week = get_week_label(week_label)
    skill_matrix = yaml.safe_load(
        (CONFIG_DIR / "skill_matrix.yaml").read_text(encoding="utf-8")
    )

    articles = get_articles_for_week(week)
    if not articles:
        articles = get_all_articles()

    # If the current week has too few strong signals (e.g. early in the week),
    # supplement with strong/weak articles from the previous 14 days.
    strong_count = sum(1 for a in articles if a.get("signal_strength") == "strong")
    if strong_count < 3:
        all_recent = get_all_articles()
        seen_ids = {a["id"] for a in articles}
        supplement = [
            a for a in all_recent
            if a["id"] not in seen_ids and a.get("signal_strength") in ("strong", "weak")
        ][:50]
        articles = articles + supplement

    strong_signals = _build_strong_signals(articles)
    weak_signals = _build_weak_signals(articles)
    noise_articles = [
        a for a in articles if a.get("signal_strength") == "noise"
    ]

    strong_section = (
        "\n\n---\n\n".join(_format_signal_entry(a) for a in strong_signals[:10])
        if strong_signals
        else "_No strong signals collected this week._"
    )

    weak_section = (
        "\n".join(
            f"- **{a['title']}** (score: {a.get('relevance_score', 0):.1f}) "
            f"— {a.get('source_name', '')} — {str(a.get('published_date', ''))[:10]}"
            for a in weak_signals[:15]
        )
        if weak_signals
        else "_No weak signals this week._"
    )

    skill_table = _build_skill_table(strong_signals, skill_matrix)
    learning_plan = _build_learning_plan(skill_matrix)
    source_list = _build_source_list(articles)
    exec_summary = _build_executive_summary(strong_signals, weak_signals, week)
    career_advice = _build_career_advice(strong_signals)
    risks_section = _build_risks_section(noise_articles)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    report = f"""# Weekly Career Intelligence Brief – {week}

_Generated: {now_str}_

---

## 1. Executive Summary

{exec_summary}

---

## 2. Strong Signals

{strong_section}

---

## 3. Weak Signals / Watchlist

{weak_section}

---

## 4. Skill Priority Update

{skill_table}

---

## 5. Recommended Learning Plan for Next Week

{learning_plan}

---

## 6. Career Positioning Advice

{career_advice}

---

## 7. Risks and Hype to Ignore

{risks_section}

---

## 8. Source List

{source_list}

---

_This report was generated by Career Intelligence Assistant (rule-based classifier, v1)._
_Human review is required before changing career direction._
_This tool is for personal career intelligence, not financial advice._
_News analysis may be incomplete or biased depending on the configured RSS sources._
"""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = REPORTS_DIR / f"weekly_career_brief_{week}.md"
    filepath.write_text(report, encoding="utf-8")
    save_report(week, str(filepath))
    return filepath
