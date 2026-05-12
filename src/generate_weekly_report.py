"""Report generator — produces Markdown and/or HTML weekly career briefs."""

import html as html_lib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

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

_LANG_FLAGS = {"en": "🇬🇧 EN", "de": "🇩🇪 DE", "zh": "🇨🇳 ZH", "ja": "🇯🇵 JA"}


def _lang_tag(article: Dict) -> str:
    lang = str(article.get("language", "en")).lower()
    return _LANG_FLAGS.get(lang, lang.upper())


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
    lang = _lang_tag(article)

    lines = [
        f"### {title}  `{lang}`",
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
    """Build the 7-column skill priority update table."""
    # Collect all tech/skill mentions from strong signals
    tech_counts: Dict[str, int] = {}
    for article in strong_signals:
        cls = _get_classification(article)
        for item in cls.get("technologies", []) + cls.get("skills", []):
            tech_counts[item.lower()] = tech_counts.get(item.lower(), 0) + 1

    # Map group → display label
    group_labels = {
        "deep_focus": "Deep Focus",
        "serious": "Serious",
        "lightweight": "Lightweight",
        "defer": "Defer",
    }

    rows: List[str] = []
    last_group: str = ""

    for skill in skill_matrix.get("skills", []):
        name = skill["name"]
        priority = skill.get("priority", 3)
        urgency = skill.get("urgency", 3)
        depth = skill.get("required_depth", 3)
        effort = f"{skill.get('weekly_hours_baseline', skill.get('weekly_hours', 1))} h"
        group = skill.get("group", "")

        # Group separator row
        if group != last_group and group in group_labels:
            label = group_labels[group]
            rows.append(f"| **{label}** | | | | | | |")
            last_group = group

        # Trigger detection against tech_counts
        triggers = [t.lower() for t in skill.get("triggers", {}).get("increase", [])]
        triggered = [t for t in triggers if t in tech_counts]

        if triggered:
            change = "↑"
            reason = f"Signals: {', '.join(triggered[:3])}"
        else:
            change = "→"
            reason = "No new signals this week"

        rows.append(
            f"| {name} | {priority}/5 | {urgency}/5 | {depth}/5 | {change} | {reason} | {effort} |"
        )

    header = "| Skill | Priority | Urgency | Req. Depth | Change | Reason | Weekly Effort |"
    separator = "|---|---|---|---|---|---|---|"
    return "\n".join([header, separator] + rows)


def _build_learning_allocation(strong_signals: List[Dict], skill_matrix: Dict) -> str:
    """Build the recommended learning allocation section grouped by strategic focus."""
    # Detect triggered skills to adjust hours
    tech_counts: Dict[str, int] = {}
    for article in strong_signals:
        cls = _get_classification(article)
        for item in cls.get("technologies", []) + cls.get("skills", []):
            tech_counts[item.lower()] = tech_counts.get(item.lower(), 0) + 1

    group_order = ["deep_focus", "serious", "lightweight", "defer"]
    group_labels = {
        "deep_focus": "Deep Focus",
        "serious": "Serious — build steadily",
        "lightweight": "Lightweight — maintain awareness",
        "defer": "Defer",
    }

    sections: List[str] = []
    grand_total = 0

    for group_key in group_order:
        group_skills = [s for s in skill_matrix.get("skills", []) if s.get("group") == group_key]
        if not group_skills:
            continue

        label = group_labels.get(group_key, group_key)
        lines = [f"**{label}**"]
        group_total = 0

        for skill in group_skills:
            base_hours = skill.get("weekly_hours_baseline", skill.get("weekly_hours", 0))
            if base_hours == 0:
                continue
            name = skill["name"]
            task = skill.get("learning_task", name)

            # Boost by 1h if strong trigger detected (cap at base + 2)
            triggers = [t.lower() for t in skill.get("triggers", {}).get("increase", [])]
            triggered = any(t in tech_counts for t in triggers)
            hours = base_hours + 1 if triggered and base_hours > 0 else base_hours
            hours = min(hours, base_hours + 2)

            lines.append(f"- **{hours} h:** {task}")
            group_total += hours

        lines.append(f"  _(Subtotal: {group_total} h)_")
        sections.append("\n".join(lines))
        grand_total += group_total

    target_note = (
        f"\n_Target: 15–20 h/week. This week total: ~{grand_total} h. "
        "Adjust defer and lightweight items to stay within your available time._"
    )
    return "\n\n".join(sections) + target_note


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

_HTML_CSS = """
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       max-width:900px;margin:0 auto;padding:20px;color:#1a1a2e;background:#f5f6fa;}
  .hdr{background:#1a1a2e;color:#fff;padding:28px 32px;border-radius:10px;margin-bottom:22px;}
  .hdr h1{margin:0 0 6px;font-size:22px;letter-spacing:-.3px;}
  .hdr .meta{color:#8892b0;font-size:13px;}
  .sec{background:#fff;border-radius:10px;padding:24px;margin-bottom:18px;
       box-shadow:0 1px 4px rgba(0,0,0,.07);}
  .sec h2{margin:0 0 16px;font-size:16px;color:#1a1a2e;border-bottom:2px solid #e8eaf0;
           padding-bottom:10px;text-transform:uppercase;letter-spacing:.5px;}
  .card{border-left:4px solid #00b894;padding:14px 16px;margin-bottom:14px;
        background:#f0fdf4;border-radius:0 8px 8px 0;}
  .card h3{margin:0 0 10px;font-size:14px;color:#1a1a2e;}
  .card dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;font-size:13px;margin:0;}
  .card dt{font-weight:600;color:#636e72;white-space:nowrap;}
  .card dd{margin:0;color:#2d3436;}
  .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;
         font-weight:600;margin-right:4px;}
  .b-high{background:#00b89420;color:#00745e;}
  .b-med{background:#fdcb6e30;color:#9d6e00;}
  .b-low{background:#e8eaf0;color:#636e72;}
  .score{background:#1a1a2e;color:#fff;padding:2px 8px;border-radius:10px;
         font-size:11px;font-weight:600;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th{background:#1a1a2e;color:#fff;padding:9px 12px;text-align:left;font-weight:600;}
  td{padding:8px 12px;border-bottom:1px solid #e8eaf0;vertical-align:top;}
  tr:nth-child(even) td{background:#fafbfc;}
  .up{color:#00b894;font-weight:700;font-size:16px;}
  .same{color:#b2bec3;font-size:16px;}
  .ph{color:#d63031;font-weight:700;}
  .pm{color:#e17055;font-weight:600;}
  .pl{color:#b2bec3;}
  .plan-item{display:flex;gap:12px;padding:7px 0;border-bottom:1px solid #f0f0f0;
             font-size:13px;}
  .plan-h{font-weight:700;min-width:36px;color:#1a1a2e;}
  ul.weak-ul{list-style:none;padding:0;margin:0;}
  ul.weak-ul li{padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:13px;}
  ul.weak-ul .ws{color:#e17055;font-weight:600;}
  ul.src-ul{list-style:none;padding:0;margin:0;}
  ul.src-ul li{padding:5px 0;border-bottom:1px solid #f0f0f0;font-size:13px;}
  a{color:#0984e3;text-decoration:none;}
  a:hover{text-decoration:underline;}
  .footer{text-align:center;color:#b2bec3;font-size:11px;padding:16px 0 4px;}
  ul.risk-ul{padding-left:20px;font-size:13px;}
  ul.risk-ul li{padding:4px 0;}
  .advice p{font-size:13px;margin:0 0 10px;}
  .exec p{font-size:14px;margin:0;}
</style>
"""


def _h(text: str) -> str:
    """HTML-escape a string."""
    return html_lib.escape(str(text))


def _html_signal_card(article: Dict) -> str:
    cls = _get_classification(article)
    score = article.get("relevance_score", 0)
    title = _h(article.get("title", "Untitled"))
    summary = _h((article.get("summary") or "")[:350].strip())
    companies = _h(", ".join(cls.get("companies", [])) or "N/A")
    regions = _h(", ".join(cls.get("regions", [])) or "N/A")
    industries = _h(", ".join(cls.get("industries", [])) or "N/A")
    techs = _h(", ".join(cls.get("technologies", [])) or "N/A")
    skills = _h(", ".join(cls.get("skills", [])) or "your profile")
    confidence = _h(article.get("confidence_level", "low"))
    action = _h(article.get("recommended_action", "watch"))
    source = _h(article.get("source_name", "Unknown"))
    pub_date = _h(str(article.get("published_date", ""))[:10])
    url = article.get("url", "")
    lang = _lang_tag(article)
    conf_class = {"high": "b-high", "medium": "b-med"}.get(confidence, "b-low")
    url_html = f'<a href="{_h(url)}" target="_blank">{_h(url[:80])}</a>' if url else "N/A"
    return f"""
<div class="card">
  <h3>{title}</h3>
  <span class="badge b-low" style="background:#e8eaf0;color:#555">{lang}</span>
  <span class="badge {conf_class}">{confidence} confidence</span>
  <span class="score">{score:.1f}/10</span>
  <dl style="margin-top:10px;">
    <dt>Development</dt><dd>{summary}</dd>
    <dt>Companies</dt><dd>{companies}</dd>
    <dt>Region</dt><dd>{regions}</dd>
    <dt>Domain</dt><dd>{industries}</dd>
    <dt>Technologies</dt><dd>{techs}</dd>
    <dt>Skills</dt><dd>{skills}</dd>
    <dt>Action</dt><dd>{action}</dd>
    <dt>Source</dt><dd>{source} — {pub_date}</dd>
    <dt>URL</dt><dd>{url_html}</dd>
  </dl>
</div>"""


def _html_skill_table(strong_signals: List[Dict], skill_matrix: Dict) -> str:
    """Build 7-column HTML skill table with group separators and 3D scoring."""
    tech_counts: Dict[str, int] = {}
    for article in strong_signals:
        cls = _get_classification(article)
        for item in cls.get("technologies", []) + cls.get("skills", []):
            tech_counts[item.lower()] = tech_counts.get(item.lower(), 0) + 1

    group_labels = {
        "deep_focus": "Deep Focus",
        "serious": "Serious — build steadily",
        "lightweight": "Lightweight — maintain awareness",
        "defer": "Defer",
    }
    group_colors = {
        "deep_focus": "#1a1a2e",
        "serious": "#2d6a4f",
        "lightweight": "#6b6b6b",
        "defer": "#999",
    }

    rows = []
    last_group = ""
    for skill in skill_matrix.get("skills", []):
        name = _h(skill["name"])
        priority = skill.get("priority", 3)
        urgency = skill.get("urgency", 3)
        depth = skill.get("required_depth", 3)
        effort = f"{skill.get('weekly_hours_baseline', skill.get('weekly_hours', 1))} h"
        group = skill.get("group", "")

        if group != last_group and group in group_labels:
            color = group_colors.get(group, "#555")
            label = group_labels[group]
            rows.append(
                f'<tr style="background:{color};color:white;">'
                f'<td colspan="7" style="font-weight:600;padding:6px 12px;">{label}</td></tr>'
            )
            last_group = group

        triggers = [t.lower() for t in skill.get("triggers", {}).get("increase", [])]
        triggered = [t for t in triggers if t in tech_counts]
        if triggered:
            arrow = '<span class="up">↑</span>'
            reason = _h(f"Signals: {', '.join(triggered[:3])}")
        else:
            arrow = '<span class="same">→</span>'
            reason = "No new signals this week"

        rows.append(
            f"<tr><td>{name}</td>"
            f"<td style='text-align:center'>{priority}/5</td>"
            f"<td style='text-align:center'>{urgency}/5</td>"
            f"<td style='text-align:center'>{depth}/5</td>"
            f"<td style='text-align:center'>{arrow}</td>"
            f"<td style='font-size:12px'>{reason}</td>"
            f"<td style='text-align:center'>{effort}</td></tr>"
        )
    header = (
        "<table><thead><tr>"
        "<th>Skill</th><th>Priority</th><th>Urgency</th><th>Req. Depth</th>"
        "<th>Change</th><th>Reason</th><th>Weekly Effort</th>"
        "</tr></thead><tbody>"
    )
    return header + "\n".join(rows) + "</tbody></table>"


def _html_learning_allocation(strong_signals: List[Dict], skill_matrix: Dict) -> str:
    """Build grouped HTML learning allocation section."""
    tech_counts: Dict[str, int] = {}
    for article in strong_signals:
        cls = _get_classification(article)
        for item in cls.get("technologies", []) + cls.get("skills", []):
            tech_counts[item.lower()] = tech_counts.get(item.lower(), 0) + 1

    group_order = ["deep_focus", "serious", "lightweight"]
    group_labels = {
        "deep_focus": "Deep Focus",
        "serious": "Serious — build steadily",
        "lightweight": "Lightweight — maintain awareness",
    }
    group_colors = {
        "deep_focus": "#f0fdf4",
        "serious": "#fffbf0",
        "lightweight": "#f5f6fa",
    }

    sections = []
    grand_total = 0

    for group_key in group_order:
        group_skills = [s for s in skill_matrix.get("skills", []) if s.get("group") == group_key]
        items = []
        group_total = 0
        for skill in group_skills:
            base = skill.get("weekly_hours_baseline", skill.get("weekly_hours", 0))
            if base == 0:
                continue
            triggers = [t.lower() for t in skill.get("triggers", {}).get("increase", [])]
            triggered = any(t in tech_counts for t in triggers)
            hours = min(base + 1 if triggered else base, base + 2)
            task = _h(skill.get("learning_task", skill["name"]))
            items.append(
                f'<div class="plan-item"><span class="plan-h">{hours} h</span><span>{task}</span></div>'
            )
            group_total += hours
        if not items:
            continue
        label = _h(group_labels.get(group_key, group_key))
        color = group_colors.get(group_key, "#f5f6fa")
        sections.append(
            f'<div style="background:{color};border-radius:8px;padding:14px;margin-bottom:12px;">'
            f'<strong style="display:block;margin-bottom:8px;">{label}</strong>'
            + "".join(items)
            + f'<p style="font-size:11px;color:#636e72;margin-top:6px;">Subtotal: {group_total} h</p>'
            + "</div>"
        )
        grand_total += group_total

    return (
        "".join(sections)
        + f'<p style="font-size:12px;color:#636e72;margin-top:4px;">'
        f'Target: 15–20 h/week · This week total: ~{grand_total} h</p>'
    )


def _render_html(
    week: str,
    strong_signals: List[Dict],
    weak_signals: List[Dict],
    noise_articles: List[Dict],
    skill_matrix: Dict,
    articles: List[Dict],
    skill_gap_html: str = "",
) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    exec_summary = _h(_build_executive_summary(strong_signals, weak_signals, week))
    career_advice = _build_career_advice(strong_signals)
    risks = _build_risks_section(noise_articles)

    # Strong signals
    if strong_signals:
        strong_html = "\n".join(_html_signal_card(a) for a in strong_signals[:10])
    else:
        strong_html = "<p><em>No strong signals collected this week.</em></p>"

    # Weak signals
    if weak_signals:
        weak_items = "".join(
            f'<li><strong>{_h(a["title"])}</strong> '
            f'<span class="ws">{a.get("relevance_score",0):.1f}</span> '
            f'— {_h(a.get("source_name",""))} — {str(a.get("published_date",""))[:10]}</li>'
            for a in weak_signals[:15]
        )
        weak_html = f'<ul class="weak-ul">{weak_items}</ul>'
    else:
        weak_html = "<p><em>No weak signals this week.</em></p>"

    # Source list
    seen: set = set()
    src_items = []
    for a in sorted(articles, key=lambda x: x.get("relevance_score", 0), reverse=True):
        url = a.get("url", "")
        if url in seen:
            continue
        seen.add(url)
        date_str = str(a.get("published_date", ""))[:10]
        title = _h(a.get("title", "Untitled"))
        src = _h(a.get("source_name", "Unknown"))
        link = f'<a class="source-link" href="{_h(url)}" target="_blank">{title}</a>' if url else title
        src_items.append(f"<li>{link} — {src} ({date_str})</li>")
    src_html = f'<ul class="src-ul">{"".join(src_items)}</ul>' if src_items else "<p><em>No sources.</em></p>"

    # Career advice (already Markdown-ish plain text — convert newlines)
    advice_html = "".join(
        f"<p>{_h(line.strip())}</p>" if line.strip() else ""
        for line in career_advice.split("\n")
    )

    # Risks (bullet list from plain text)
    risk_lines = [l.lstrip("- ").strip() for l in risks.split("\n") if l.strip().startswith("-")]
    risk_html = "<ul class='risk-ul'>" + "".join(f"<li>{_h(l)}</li>" for l in risk_lines) + "</ul>"

    skill_gap_section = ""
    if skill_gap_html:
        skill_gap_section = f"""
<div class="sec">
  <h2>9. Skill Gap Analysis</h2>
  {skill_gap_html}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Career Intelligence Brief – {_h(week)}</title>
{_HTML_CSS}
</head>
<body>

<div class="hdr">
  <h1>Weekly Career Intelligence Brief – {_h(week)}</h1>
  <div class="meta">Generated: {_h(now_str)}</div>
</div>

<div class="sec exec">
  <h2>1. Executive Summary</h2>
  <p>{exec_summary}</p>
</div>

<div class="sec">
  <h2>2. Strong Signals</h2>
  {strong_html}
</div>

<div class="sec">
  <h2>3. Weak Signals / Watchlist</h2>
  {weak_html}
</div>

<div class="sec">
  <h2>4. Skill Priority Update</h2>
  {_html_skill_table(strong_signals, skill_matrix)}
</div>

<div class="sec">
  <h2>5. Recommended Learning Allocation for Next Week</h2>
  {_html_learning_allocation(strong_signals, skill_matrix)}
</div>

<div class="sec advice">
  <h2>6. Career Positioning Advice</h2>
  {advice_html}
</div>

<div class="sec">
  <h2>7. Risks and Hype to Ignore</h2>
  {risk_html}
</div>

<div class="sec">
  <h2>8. Source List</h2>
  {src_html}
</div>

{skill_gap_section}

<div class="footer">
  Career Intelligence Assistant · Rule-based classifier v1 ·
  Human review required before changing career direction. Not financial advice.
</div>

</body>
</html>"""


def generate_report(
    week_label: Optional[str] = None,
    fmt: Literal["md", "html", "both"] = "both",
    skill_gap_html: str = "",
) -> Dict[str, Path]:
    """Generate and save the weekly report.

    Args:
        week_label: 'current', 'last', or 'YYYY-WW'.
        fmt: output format — 'md', 'html', or 'both' (default).
        skill_gap_html: optional pre-rendered HTML block for Section 9.

    Returns:
        Dict mapping format key ('md', 'html') to saved file Path.
    """
    init_db()
    week = get_week_label(week_label)
    skill_matrix = yaml.safe_load(
        (CONFIG_DIR / "skill_matrix.yaml").read_text(encoding="utf-8")
    )

    articles = get_articles_for_week(week)
    if not articles:
        articles = get_all_articles()

    # Supplement if the week just started and has few strong signals
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
    noise_articles = [a for a in articles if a.get("signal_strength") == "noise"]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    saved: Dict[str, Path] = {}

    # --- Markdown ---
    if fmt in ("md", "both"):
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
        skill_gap_md = ""
        if skill_gap_html:
            skill_gap_md = "\n\n---\n\n## 9. Skill Gap Analysis\n\n_(See HTML version for full table.)_"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        report_md = f"""# Weekly Career Intelligence Brief – {week}

_Generated: {now_str}_

---

## 1. Executive Summary

{_build_executive_summary(strong_signals, weak_signals, week)}

---

## 2. Strong Signals

{strong_section}

---

## 3. Weak Signals / Watchlist

{weak_section}

---

## 4. Skill Priority Update

{_build_skill_table(strong_signals, skill_matrix)}

---

## 5. Recommended Learning Allocation for Next Week

{_build_learning_allocation(strong_signals, skill_matrix)}

---

## 6. Career Positioning Advice

{_build_career_advice(strong_signals)}

---

## 7. Risks and Hype to Ignore

{_build_risks_section(noise_articles)}

---

## 8. Source List

{_build_source_list(articles)}{skill_gap_md}

---

_Career Intelligence Assistant · rule-based classifier v1_
_Human review required before changing career direction. Not financial advice._
"""
        md_path = REPORTS_DIR / f"weekly_career_brief_{week}.md"
        md_path.write_text(report_md, encoding="utf-8")
        saved["md"] = md_path

    # --- HTML ---
    if fmt in ("html", "both"):
        html_content = _render_html(
            week, strong_signals, weak_signals, noise_articles,
            skill_matrix, articles, skill_gap_html,
        )
        html_path = REPORTS_DIR / f"weekly_career_brief_{week}.html"
        html_path.write_text(html_content, encoding="utf-8")
        saved["html"] = html_path

    save_report(week, str(saved.get("md") or saved.get("html")))
    return saved
