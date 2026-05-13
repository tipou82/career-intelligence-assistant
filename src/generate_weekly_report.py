"""Report generator — produces Markdown and/or HTML weekly career briefs."""

import html as html_lib
import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml

from .database import get_all_articles, get_articles_for_week, get_job_ads, init_db, save_report
from .qualification_layer import build_qualification_md, build_qualification_html, load_and_score

CONFIG_DIR = Path(__file__).parent.parent / "config"
REPORTS_DIR = Path(__file__).parent.parent / "reports"


def _load_career_mode() -> str:
    try:
        data = yaml.safe_load((CONFIG_DIR / "skill_matrix.yaml").read_text(encoding="utf-8"))
        return str(data.get("career_mode", "default"))
    except Exception:
        return "default"


def _load_weekly_hours_cap() -> int:
    try:
        data = yaml.safe_load((CONFIG_DIR / "skill_matrix.yaml").read_text(encoding="utf-8"))
        return int(data.get("weekly_hours_cap", 20))
    except Exception:
        return 20


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


def _build_learning_allocation(
    strong_signals: List[Dict],
    skill_matrix: Dict,
    hours_cap: int = 20,
) -> str:
    """Build the recommended learning allocation, respecting the weekly hours cap."""
    tech_counts: Dict[str, int] = {}
    for article in strong_signals:
        cls = _get_classification(article)
        for item in cls.get("technologies", []) + cls.get("skills", []):
            tech_counts[item.lower()] = tech_counts.get(item.lower(), 0) + 1

    group_order = ["deep_focus", "serious", "lightweight", "defer"]
    group_labels = {
        "deep_focus": skill_matrix.get("groups", {}).get("deep_focus", {}).get("label", "Deep Focus"),
        "serious": skill_matrix.get("groups", {}).get("serious", {}).get("label", "Serious"),
        "lightweight": skill_matrix.get("groups", {}).get("lightweight", {}).get("label", "Lightweight"),
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
            # Stop adding hours if cap already reached
            if grand_total + group_total >= hours_cap:
                break
            task = skill.get("learning_task", skill["name"])
            triggers = [t.lower() for t in skill.get("triggers", {}).get("increase", [])]
            triggered = any(t in tech_counts for t in triggers)
            hours = min(base_hours + 1 if triggered else base_hours, base_hours + 2)
            # Clamp to remaining budget
            remaining = hours_cap - grand_total - group_total
            hours = min(hours, remaining)
            if hours <= 0:
                break
            lines.append(f"- **{hours} h:** {task}")
            group_total += hours

        if group_total > 0:
            lines.append(f"  _(Subtotal: {group_total} h)_")
            sections.append("\n".join(lines))
            grand_total += group_total

    over_note = " ⚠️ Cap applied." if grand_total >= hours_cap else ""
    target_note = (
        f"\n_Weekly total: ~{grand_total} h (cap: {hours_cap} h).{over_note} "
        "Prioritise Deep Focus items — job search first._"
    )
    return "\n\n".join(sections) + target_note


def _build_career_actions_section(
    articles: List[Dict],
    skill_matrix: Dict,
    career_mode: str,
) -> str:
    """Section 2a: Career Actions This Week — concrete steps for the next 7 days."""
    if career_mode != "external_transition":
        return ""

    # Collect company signals from all strong+weak articles
    company_counts: Counter = Counter()
    tech_counts: Counter = Counter()
    region_counts: Counter = Counter()
    industry_counts: Counter = Counter()
    high_actionability = []

    for a in articles:
        if a.get("signal_strength") not in ("strong", "weak"):
            continue
        cls = _get_classification(a)
        for c in cls.get("companies", []):
            company_counts[c] += 1
        for t in cls.get("technologies", []) + cls.get("skills", []):
            tech_counts[t.lower()] += 1
        for r in cls.get("regions", []):
            region_counts[r.lower()] += 1
        for i in cls.get("industries", []):
            industry_counts[i.lower()] += 1
        if a.get("career_actionability_score", 0) >= 6.0:
            high_actionability.append(a)

    # Top job clusters aligned with Xi's cultural-PM target roles
    job_clusters = [
        "Projektmanager*in Kultur (Konzerthaus / Festival / Kulturamt)",
        "Bildungsreferent*in Musik / Kulturelle Bildung (Musikvermittlung)",
        "Veranstaltungsmanager*in Kultur (Eventagentur / Festival)",
        "Education / Outreach Manager (Konzerthaus / Musikhochschule)",
        "Pressereferent*in / Kommunikation (Kulturinstitution)",
    ]

    # Top companies from signals (filter for cultural-sector relevance)
    top_companies = [c for c, _ in company_counts.most_common(8)][:5]
    if not top_companies:
        top_companies = [
            "Stuttgarter Liederhalle",
            "Musikhochschule Stuttgart (HMDK)",
            "Stuttgarter Philharmoniker",
            "Schlossfestspiele Ludwigsburg",
            "Kulturamt Leonberg",
        ]

    # Recommended application keywords (top tech tags)
    keywords = [t for t, _ in tech_counts.most_common(10)
                if len(t) > 3][:8]

    # Suggested networking targets
    networking = [
        "Musikhochschule Stuttgart (HMDK) alumni and Education-Manager-Team",
        "Kulturmanagement Network (kulturmanagement.net) and LinkedIn group",
        "Netzwerk Junge Ohren — Musikvermittlung professionals",
        "Stuttgarter Liederhalle and Schlossfestspiele Ludwigsburg press teams",
        "Kulturamt Leonberg / Stuttgart Veranstaltungskoordination",
    ]

    # Concrete 7-day action plan
    plan_lines = [
        "1. **Apply** to 3 tailored cultural-PM roles in BW (priority: education, event production)",
        "2. **Update LinkedIn headline** → 'Projektmanagerin Kultur — Bildung, Veranstaltung, Kommunikation'",
        "3. **Contact** one Stuttgart-area cultural professional for a 20-minute Kennenlerngespräch",
        "4. **Practice** one STAR interview answer aloud in German with Sprachcoach or tandem partner",
        "5. **Advance** one Google PM or Scrum Master I module; log progress to certification tracker",
    ]

    lines = [
        "### Top 5 Role Clusters to Target",
        "\n".join(f"- {c}" for c in job_clusters),
        "",
        "### Top Companies to Monitor or Approach",
        "\n".join(f"- {c}" for c in top_companies),
        "",
        "### Recommended CV / Application Keywords",
        ", ".join(f"`{k}`" for k in keywords) if keywords else "_Based on this week's signals — update after classify._",
        "",
        "### Networking Targets",
        "\n".join(f"- {n}" for n in networking),
        "",
        "### 7-Day Concrete Action Plan",
        "\n".join(plan_lines),
    ]
    return "\n".join(lines)


def _build_market_fit_section(articles: List[Dict], career_mode: str) -> str:
    """Section: External Market Fit — profile mapping to target industries."""
    if career_mode != "external_transition":
        return ""

    industry_signals: Dict[str, List[str]] = {
        "education_programs": [],
        "event_production": [],
        "music_classical": [],
        "museum_exhibition": [],
        "pr_communication": [],
    }

    for a in articles:
        if a.get("signal_strength") not in ("strong", "weak"):
            continue
        cls = _get_classification(a)
        inds = {i.lower() for i in cls.get("industries", [])}
        techs = {t.lower() for t in cls.get("technologies", []) + cls.get("skills", [])}
        title = a.get("title", "")[:60]

        if inds & {"education_programs"} or \
           techs & {"musikvermittlung", "konzertpädagogik", "bildungsreferent",
                    "kulturelle bildung", "music education", "outreach"}:
            industry_signals["education_programs"].append(title)
        if inds & {"event_production"} or \
           techs & {"veranstaltungsmanagement", "eventmanagement", "konzertdirektion",
                    "festival", "künstlerbetreuung"}:
            industry_signals["event_production"].append(title)
        if inds & {"music_classical"} or \
           techs & {"orchester", "philharmonie", "konzerthaus", "oper",
                    "klassik", "klassische musik", "theater"}:
            industry_signals["music_classical"].append(title)
        if inds & {"museum_exhibition"} or \
           techs & {"museum", "ausstellung", "museumspädagogik", "galerie"}:
            industry_signals["museum_exhibition"].append(title)
        if inds & {"pr_communication"} or \
           techs & {"pressearbeit", "öffentlichkeitsarbeit", "kommunikation",
                    "social media", "newsletter"}:
            industry_signals["pr_communication"].append(title)

    profile_map = {
        "education_programs": {
            "label": "🎓 Education Programs / Musikvermittlung (Priority #1)",
            "fit": "**Strong match** — musicology degree + conservatoire background + CNSO experience. "
                   "Target: Bildungsreferent*in at Stuttgarter Liederhalle, HMDK, Musikschulen.",
            "signal_label": "Active signals this week",
        },
        "event_production": {
            "label": "🎪 Event Production & Coordination (Priority #2)",
            "fit": "**Good match** — 5 years concert-event coordination at CNSO. "
                   "DE gap: learn Reservix/Eventim, GEMA, KSK on the job.",
            "signal_label": "Active signals this week",
        },
        "music_classical": {
            "label": "🎼 Music Institutions (Concert Halls, Opera, Drama) (Priority #3)",
            "fit": "**Natural home** — deep classical music credibility. "
                   "Target: Orchesterakademie roles, Dramaturgieassistenz, Künstlerisches Betriebsbüro.",
            "signal_label": "Active signals this week",
        },
        "museum_exhibition": {
            "label": "🖼️ Exhibitions & Museums (Priority #4)",
            "fit": "**Moderate match** — cultural-PM transferability is real; "
                   "pursue only if direct vacancy appears at Staatsgalerie, Kunstmuseum or Linden-Museum.",
            "signal_label": "Active signals this week",
        },
        "pr_communication": {
            "label": "📣 PR & Communication (Lateral track)",
            "fit": "**Fluent** — CNSO press work is the strongest existing credential. "
                   "Use as secondary pitch, not primary identity. German writing quality is the key gate.",
            "signal_label": "Active signals this week",
        },
    }

    lines = []
    for key, meta in profile_map.items():
        signals = industry_signals[key][:3]
        lines.append(f"**{meta['label']}**")
        lines.append(f"Profile fit: {meta['fit']}")
        if signals:
            lines.append(f"{meta['signal_label']}:")
            lines.extend(f"  - {s}" for s in signals)
        else:
            lines.append(f"_{meta['signal_label']}: none this week._")
        lines.append("")

    return "\n".join(lines).strip()


def _build_job_ads_md(job_ads: List[Dict]) -> str:
    if not job_ads:
        return "_No job ads with score ≥ 6 found in the database._"
    lines: List[str] = []
    for a in job_ads:
        url = a.get("url", "")
        title = a.get("title", "Untitled")
        linked = f"[{title}]({url})" if url else title
        score = a.get("relevance_score", 0)
        source = a.get("source_name", "")
        pub_date = str(a.get("published_date", ""))[:10]
        cls = _get_classification(a)
        regions = ", ".join(cls.get("regions", [])) or "N/A"
        skills = ", ".join(cls.get("skills", [])) or "N/A"
        lines.append(
            f"- **{linked}** (score: {score:.1f}) — {source} — {pub_date}  \n"
            f"  Region: {regions} · Skills: {skills}"
        )
    return "\n".join(lines)


def _build_job_ads_html(job_ads: List[Dict]) -> str:
    if not job_ads:
        return "<p><em>No job ads with score ≥ 6 found in the database.</em></p>"
    items: List[str] = []
    for a in job_ads:
        url = a.get("url", "")
        title = _h(a.get("title", "Untitled"))
        score = a.get("relevance_score", 0)
        source = _h(a.get("source_name", ""))
        pub_date = _h(str(a.get("published_date", ""))[:10])
        cls = _get_classification(a)
        regions = _h(", ".join(cls.get("regions", [])) or "N/A")
        skills = _h(", ".join(cls.get("skills", [])) or "N/A")
        link = f'<a href="{_h(url)}" target="_blank">{title}</a>' if url else title
        items.append(
            f'<li style="padding:7px 0;border-bottom:1px solid #f0f0f0;font-size:13px;">'
            f'<strong>{link}</strong> '
            f'<span class="score" style="background:#d63031">{score:.1f}/10</span><br>'
            f'<span style="font-size:12px;color:#636e72">'
            f'Region: {regions} · Skills: {skills} · {source} — {pub_date}'
            f'</span></li>'
        )
    return f'<ul style="list-style:none;padding:0;margin:0">{"".join(items)}</ul>'


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
            "No major signals this week. Continue current priorities: job applications "
            "(3+ per week), spoken German practice, and Google PM / Scrum Master I "
            "module completion.\n\n"
            "Maintain the bilingual CV and LinkedIn profile update rhythm — "
            "one refined bullet per week is enough to keep momentum."
        )
    industries: set = set()
    techs: set = set()
    for a in strong_signals:
        cls = _get_classification(a)
        industries.update(i.lower() for i in cls.get("industries", []))
        techs.update(t.lower() for t in cls.get("technologies", []) + cls.get("skills", []))

    parts = [
        "Based on this week's signals, your positioning as a "
        "**multilingual cultural project manager for the Stuttgart region** remains sound.\n"
    ]
    if "education_programs" in industries or \
       techs & {"musikvermittlung", "bildungsreferent", "kulturelle bildung", "konzertpädagogik"}:
        parts.append(
            "**Musikvermittlung / education-program signals are active.** "
            "This is your sub-sector #1 — check vacancies at HMDK Stuttgart, "
            "Liederhalle, and Netzwerk Junge Ohren this week.\n"
        )
    if "event_production" in industries or \
       techs & {"veranstaltungsmanagement", "festival", "konzertdirektion"}:
        parts.append(
            "**Event-production activity visible.** "
            "Scan Schlossfestspiele Ludwigsburg, SKS Russ and Theaterhaus Stuttgart "
            "for coordinator / PM openings.\n"
        )
    if "funding_policy" in industries or \
       techs & {"kulturförderung", "fördermittel", "drittmittel", "förderaufruf"}:
        parts.append(
            "**Funding or cultural-policy news detected.** "
            "Note any budget changes at local cultural institutions — they signal "
            "staffing changes in 3–6 months.\n"
        )
    if not parts[1:]:
        parts.append(
            "Signals this week are broad. No specific pivot recommended. "
            "Maintain weekly application rhythm and spoken-German practice.\n"
        )
    return "\n".join(parts)


def _build_risks_section(noise_articles: List[Dict]) -> str:
    warnings = [
        "- **Celebrity / artist gossip or scandal news:** Not actionable for job search "
        "unless it signals leadership change at a target organisation.",
        "- **Concert reviews and programme notes without hiring signal:** "
        "Interesting background reading; do not interrupt application workflow.",
        "- **Generic 'AI in culture' hype pieces:** Only actionable if tied to a specific "
        "tool or vacancy at a target institution.",
        "- **National or international music prizes / competitions:** "
        "Good for network awareness; follow up only if a target org is involved.",
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
    career_mode: str = "default",
    career_actions_md: str = "",
    market_fit_md: str = "",
    weak_signals_rest_count: int = 0,
    hours_cap: int = 20,
    qualification_html: str = "",
    job_ads_html: str = "",
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

    # Weak signals — show top 15 with actionability score
    if weak_signals:
        def _weak_item_html(a: Dict) -> str:
            url = a.get("url", "")
            title = _h(a.get("title", ""))
            linked = f'<a href="{_h(url)}" target="_blank">{title}</a>' if url else title
            score = a.get("relevance_score", 0)
            act = a.get("career_actionability_score", 0)
            source = _h(a.get("source_name", ""))
            date_str2 = str(a.get("published_date", ""))[:10]
            lang = _lang_tag(a)
            return (
                f'<li><strong>{linked}</strong> '
                f'<span style="font-size:11px;color:#888">{lang}</span> '
                f'<span class="ws">{score:.1f}</span> '
                f'<span style="font-size:11px;color:#00b894">act:{act:.1f}</span> '
                f'— {source} — {date_str2}</li>'
            )
        weak_items = "".join(_weak_item_html(a) for a in weak_signals)
        rest_note = (
            f'<p style="font-size:12px;color:#636e72;margin-top:6px;">'
            f'+ {weak_signals_rest_count} further signals not shown (low actionability).</p>'
            if weak_signals_rest_count > 0 else ""
        )
        weak_html = f'<ul class="weak-ul">{weak_items}</ul>{rest_note}'
    else:
        weak_html = "<p><em>No weak signals this week.</em></p>"

    # Source list — only strong + shown weak (not full dump)
    top_articles = strong_signals + weak_signals
    seen: set = set()
    src_items = []
    for a in sorted(top_articles, key=lambda x: x.get("relevance_score", 0), reverse=True):
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

    # Career advice
    advice_html = "".join(
        f"<p>{_h(line.strip())}</p>" if line.strip() else ""
        for line in career_advice.split("\n")
    )

    # Risks
    risk_lines = [l.lstrip("- ").strip() for l in risks.split("\n") if l.strip().startswith("-")]
    risk_html = "<ul class='risk-ul'>" + "".join(f"<li>{_h(l)}</li>" for l in risk_lines) + "</ul>"

    # Career Actions section (external_transition mode only)
    career_actions_section_html = ""
    if career_actions_md:
        ca_lines = []
        for line in career_actions_md.split("\n"):
            if line.startswith("### "):
                ca_lines.append(f'<h4 style="margin:14px 0 6px">{_h(line[4:])}</h4>')
            elif line.startswith("- "):
                ca_lines.append(f'<li style="font-size:13px">{_h(line[2:])}</li>')
            elif line.strip():
                ca_lines.append(f'<p style="font-size:13px">{_h(line)}</p>')
        career_actions_section_html = f"""
<div class="sec" style="border-left:4px solid #d63031;padding-left:20px">
  <h2>2. Career Actions This Week</h2>
  {"".join(ca_lines)}
</div>"""

    # Market Fit section
    market_fit_section_html = ""
    if market_fit_md:
        mf_lines = []
        for line in market_fit_md.split("\n"):
            if line.startswith("**"):
                mf_lines.append(f'<p style="font-size:13px;font-weight:600">{_h(line.strip("*"))}</p>')
            elif line.startswith("  - "):
                mf_lines.append(f'<li style="font-size:12px;color:#636e72">{_h(line[4:])}</li>')
            elif line.strip():
                mf_lines.append(f'<p style="font-size:13px">{_h(line)}</p>')
        market_fit_section_html = f"""
<div class="sec" style="background:#f8f9fa">
  <h2>External Market Fit</h2>
  {"".join(mf_lines)}
</div>"""

    skill_gap_section = ""
    if skill_gap_html:
        skill_gap_section = f"""
<div class="sec">
  <h2>Skill Gap Analysis</h2>
  {skill_gap_html}
</div>"""

    qualification_section_html = ""
    if qualification_html:
        qualification_section_html = f"""
<div class="sec" style="border-top:3px solid #1a1a2e;margin-top:24px">
  <h2>Qualification Actions This Week</h2>
  {qualification_html}
</div>"""

    job_ads_section_html = f"""
<div class="sec" style="border-left:4px solid #d63031;padding-left:20px">
  <h2>{1 + (1 if career_actions_md else 0) + 1}. Job Ads (score &ge; 6)</h2>
  {job_ads_html}
</div>"""

    mode_badge = (
        f'<span style="background:#d63031;color:white;padding:2px 8px;border-radius:4px;'
        f'font-size:11px;font-weight:600">{career_mode.replace("_", " ").upper()}</span> '
        if career_mode != "default" else ""
    )

    sec = lambda n: n + (1 if career_actions_md else 0) + 1  # +1 career actions, +1 job ads

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
  <div class="meta">{mode_badge}Generated: {_h(now_str)}</div>
</div>

<div class="sec exec">
  <h2>1. Executive Summary</h2>
  <p>{exec_summary}</p>
</div>

{career_actions_section_html}

{job_ads_section_html}

<div class="sec">
  <h2>{sec(2)}. Strong Signals</h2>
  {strong_html}
</div>

<div class="sec">
  <h2>{sec(3)}. Weak Signals / Watchlist <small style="color:#636e72;font-weight:normal">(top 15 by actionability)</small></h2>
  {weak_html}
</div>

<div class="sec">
  <h2>{sec(4)}. Skill Priority Update</h2>
  {_html_skill_table(strong_signals, skill_matrix)}
</div>

<div class="sec">
  <h2>{sec(5)}. Recommended Learning Allocation</h2>
  {_html_learning_allocation(strong_signals, skill_matrix)}
</div>

<div class="sec advice">
  <h2>{sec(6)}. Career Positioning Advice</h2>
  {advice_html}
</div>

<div class="sec">
  <h2>{sec(7)}. Risks and Hype to Ignore</h2>
  {risk_html}
</div>

{market_fit_section_html}

<div class="sec">
  <h2>{sec(8)}. Source List</h2>
  {src_html}
</div>

{skill_gap_section}

{qualification_section_html}

<div class="footer">
  Career Intelligence Assistant · {_h(career_mode)} mode ·
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
    career_mode = _load_career_mode()
    hours_cap = _load_weekly_hours_cap()

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
    # Sort weak signals by career_actionability_score desc, then by relevance
    all_weak = _build_weak_signals(articles)
    all_weak_sorted = sorted(
        all_weak,
        key=lambda a: (a.get("career_actionability_score", 0), a.get("relevance_score", 0)),
        reverse=True,
    )
    weak_signals_top = all_weak_sorted[:15]     # top 15 by actionability
    weak_signals_rest = all_weak_sorted[15:]    # remainder → summarised by theme
    noise_articles = [a for a in articles if a.get("signal_strength") == "noise"]

    job_ads = get_job_ads(min_score=6.0)

    # Pre-compute new sections (only non-empty in external_transition mode)
    career_actions_md = _build_career_actions_section(articles, skill_matrix, career_mode)
    market_fit_md = _build_market_fit_section(articles, career_mode)

    # Load qualification actions (silently skip if config missing)
    qual_data = load_and_score()
    _qual_data_html = build_qualification_html(qual_data) if qual_data["scored_actions"] else ""
    _qual_data_md   = build_qualification_md(qual_data)   if qual_data["scored_actions"] else ""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    saved: Dict[str, Path] = {}

    # --- Markdown ---
    if fmt in ("md", "both"):
        strong_section = (
            "\n\n---\n\n".join(_format_signal_entry(a) for a in strong_signals[:10])
            if strong_signals
            else "_No strong signals collected this week._"
        )

        def _weak_line(a: Dict) -> str:
            url = a.get("url", "")
            title = a["title"]
            linked = f"[{title}]({url})" if url else title
            score = a.get("relevance_score", 0)
            act = a.get("career_actionability_score", 0)
            source = a.get("source_name", "")
            date_str = str(a.get("published_date", ""))[:10]
            lang = _lang_tag(a)
            return f"- **{linked}** `{lang}` (rel: {score:.1f} · act: {act:.1f}) — {source} — {date_str}"

        weak_section = (
            "\n".join(_weak_line(a) for a in weak_signals_top)
            if weak_signals_top
            else "_No weak signals this week._"
        )

        # Summarise the rest by industry theme
        rest_summary = ""
        if weak_signals_rest:
            theme_counts: Counter = Counter()
            for a in weak_signals_rest:
                cls = _get_classification(a)
                for i in cls.get("industries", []):
                    theme_counts[i] += 1
            top_themes = ", ".join(f"{t} ({n})" for t, n in theme_counts.most_common(5))
            rest_summary = (
                f"\n\n_+ {len(weak_signals_rest)} further weak signals not shown. "
                f"Main themes: {top_themes}._"
            )

        # Section numbering: 1=Exec, 2=CareerActions(optional), N=JobAds, N+1=Strong, ...
        sec_offset = (1 if career_actions_md else 0) + 1  # +1 for job ads section
        s = lambda n: n + sec_offset

        sec_job_ads = 1 + (1 if career_actions_md else 0) + 1

        career_actions_section = ""
        if career_actions_md:
            career_actions_section = f"\n\n---\n\n## 2. Career Actions This Week\n\n{career_actions_md}"

        job_ads_section = (
            f"\n\n---\n\n## {sec_job_ads}. Job Ads (score ≥ 6)\n\n"
            f"{_build_job_ads_md(job_ads)}"
        )

        market_fit_section = ""
        if market_fit_md:
            market_fit_section = f"\n\n---\n\n## External Market Fit\n\n{market_fit_md}"

        skill_gap_md = ""
        if skill_gap_html:
            skill_gap_md = "\n\n---\n\n## Skill Gap Analysis\n\n_(See HTML version for full table.)_"

        qualification_md_section = ""
        if _qual_data_md:
            person = qual_data.get("strategy", {}).get("target_person", "")
            header = f"Qualification Actions This Week" + (f" — {person}" if person else "")
            qualification_md_section = f"\n\n---\n\n## {header}\n\n{_qual_data_md}"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        mode_line = f"_Mode: **{career_mode.replace('_', ' ').title()}** · " if career_mode != "default" else "_"
        report_md = f"""# Weekly Career Intelligence Brief – {week}

{mode_line}Generated: {now_str}_

---

## 1. Executive Summary

{_build_executive_summary(strong_signals, all_weak, week)}{career_actions_section}{job_ads_section}

---

## {s(2)}. Strong Signals

{strong_section}

---

## {s(3)}. Weak Signals / Watchlist _(top 15 by actionability)_

{weak_section}{rest_summary}

---

## {s(4)}. Skill Priority Update

{_build_skill_table(strong_signals, skill_matrix)}

---

## {s(5)}. Recommended Learning Allocation for Next Week

{_build_learning_allocation(strong_signals, skill_matrix, hours_cap=hours_cap)}

---

## {s(6)}. Career Positioning Advice

{_build_career_advice(strong_signals)}

---

## {s(7)}. Risks and Hype to Ignore

{_build_risks_section(noise_articles)}{market_fit_section}

---

## {s(8)}. Source List _(top articles only)_

{_build_source_list(strong_signals + weak_signals_top)}{skill_gap_md}{qualification_md_section}

---

_Career Intelligence Assistant · {career_mode} mode_
_Human review required before changing career direction. Not financial advice._
"""
        md_path = REPORTS_DIR / f"weekly_career_brief_{week}.md"
        md_path.write_text(report_md, encoding="utf-8")
        saved["md"] = md_path

    # --- HTML ---
    if fmt in ("html", "both"):
        html_content = _render_html(
            week, strong_signals, weak_signals_top, noise_articles,
            skill_matrix, articles, skill_gap_html,
            career_mode=career_mode,
            career_actions_md=career_actions_md,
            market_fit_md=market_fit_md,
            weak_signals_rest_count=len(weak_signals_rest),
            hours_cap=hours_cap,
            qualification_html=_qual_data_html,
            job_ads_html=_build_job_ads_html(job_ads),
        )
        html_path = REPORTS_DIR / f"weekly_career_brief_{week}.html"
        html_path.write_text(html_content, encoding="utf-8")
        saved["html"] = html_path

    save_report(week, str(saved.get("md") or saved.get("html")))
    return saved
