"""Skill gap analysis — compares CV self-ratings against job market demand signals.

Data sources:
  - config/cv_skills.yaml  : your current self-rated skill claims
  - config/skill_matrix.yaml: target skill priorities
  - job_signals table (from collect_jobs): live job posting counts per skill tag
  - strong/weak article signals: technology mentions from the news pipeline

Outputs a structured gap report that is embedded in Section 9 of the weekly report.

Run standalone:
    python -m src.main skill-gap
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

# Skill name → job_signals skill_tag mapping (lowercase)
_SKILL_TO_TAG: Dict[str, str] = {
    "ros2": "ros2",
    "iso 26262": "iso_26262",
    "functional safety": "functional_safety",
    "sotif": "sotif",
    "iso/pas 8800": "iso_pas_8800",
    "embedded ai": "embedded_ai",
    "adas": "adas",
    "qnx": "qnx",
    "mbse / sysml2": "mbse",
    "c++20": "c++20",
    "embedded linux": "embedded",
    "fault injection testing": "functional_safety",
    "ai perception monitoring": "embedded_ai",
    "digital twin / virtual validation": "digital_twin",
}

# Job demand tier thresholds (posting count from bundesagentur/indeed)
_DEMAND_HIGH = 50
_DEMAND_MED = 15


def _load_cv_skills() -> List[Dict[str, Any]]:
    path = CONFIG_DIR / "cv_skills.yaml"
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("skills", [])


def _load_skill_matrix() -> List[Dict[str, Any]]:
    path = CONFIG_DIR / "skill_matrix.yaml"
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("skills", [])


def _get_job_demand() -> Dict[str, int]:
    """Aggregate job posting counts by skill tag from the database."""
    try:
        from .collect_jobs import get_job_trends_summary
        return get_job_trends_summary()
    except Exception:
        return {}


def _demand_label(count: int) -> str:
    if count >= _DEMAND_HIGH:
        return "High"
    if count >= _DEMAND_MED:
        return "Medium"
    if count > 0:
        return "Low"
    return "Unknown"


def _gap_label(self_rating: int, demand: str) -> Tuple[str, str]:
    """Return (gap_level, recommendation).

    gap_level: 'critical' | 'moderate' | 'minor' | 'ok'
    """
    if demand == "High" and self_rating < 4:
        return "critical", "Prioritise immediately — high market demand, low current level"
    if demand in ("High", "Medium") and self_rating < 6:
        return "moderate", "Build steadily — market demand justifies consistent weekly time"
    if demand == "High" and self_rating >= 6:
        return "ok", "Good standing — maintain and deepen"
    if self_rating < 3:
        return "minor", "Low demand signal or early-stage — continue at current pace"
    return "ok", "On track"


def analyse_skill_gap() -> Dict[str, Any]:
    """Run the gap analysis and return structured results."""
    cv_skills = _load_cv_skills()
    matrix_skills = _load_skill_matrix()
    job_demand = _get_job_demand()

    # Build a lookup: lowercase skill name → cv entry
    cv_lookup: Dict[str, Dict] = {s["name"].lower(): s for s in cv_skills}

    # Build a lookup: matrix skill name → weekly hours
    matrix_lookup: Dict[str, int] = {
        s["name"].lower(): s.get("weekly_hours", 1) for s in matrix_skills
    }

    rows: List[Dict[str, Any]] = []

    # Analyse every skill in the skill matrix
    for ms in matrix_skills:
        name = ms["name"]
        name_lower = name.lower()
        cv_entry = cv_lookup.get(name_lower, {})
        self_rating = int(cv_entry.get("self_rating", 0))
        cv_claimed = bool(cv_entry.get("cv_claimed", False))
        tag = _SKILL_TO_TAG.get(name_lower, name_lower.replace(" ", "_").replace("/", "_"))
        demand_count = job_demand.get(tag, 0)
        demand = _demand_label(demand_count)
        gap_level, recommendation = _gap_label(self_rating, demand)

        rows.append({
            "skill": name,
            "self_rating": self_rating,
            "cv_claimed": cv_claimed,
            "demand": demand,
            "demand_count": demand_count,
            "priority": ms.get("priority", "medium"),
            "weekly_hours": ms.get("weekly_hours", 1),
            "gap_level": gap_level,
            "recommendation": recommendation,
        })

    # Sort: critical → moderate → minor → ok
    order = {"critical": 0, "moderate": 1, "minor": 2, "ok": 3}
    rows.sort(key=lambda r: (order.get(r["gap_level"], 4), -r.get("demand_count", 0)))

    critical = [r for r in rows if r["gap_level"] == "critical"]
    moderate = [r for r in rows if r["gap_level"] == "moderate"]

    return {
        "rows": rows,
        "critical": critical,
        "moderate": moderate,
        "job_demand": job_demand,
    }


def render_gap_html(gap_data: Dict[str, Any]) -> str:
    """Render the gap analysis as an HTML fragment for embedding in the report."""
    import html as html_lib

    def h(s: str) -> str:
        return html_lib.escape(str(s))

    rows = gap_data["rows"]
    if not rows:
        return "<p><em>No skill gap data available. Run <code>collect-jobs</code> first for live demand figures.</em></p>"

    gap_colors = {
        "critical": ("#d63031", "#fff5f5"),
        "moderate": ("#e17055", "#fffaf0"),
        "minor":    ("#636e72", "#f8f9fa"),
        "ok":       ("#00b894", "#f0fdf4"),
    }

    demand_icon = {"High": "🔴", "Medium": "🟡", "Low": "🟢", "Unknown": "⚪"}

    header = """
<table>
  <thead><tr>
    <th>Skill</th><th>Self-Rating</th><th>CV?</th>
    <th>Market Demand</th><th>Gap Level</th><th>Recommendation</th>
  </tr></thead>
  <tbody>"""

    table_rows = []
    for r in rows:
        color, bg = gap_colors.get(r["gap_level"], ("#636e72", "#f8f9fa"))
        demand_str = f"{demand_icon.get(r['demand'], '')} {h(r['demand'])}"
        if r["demand_count"] > 0:
            demand_str += f" ({r['demand_count']} postings)"
        rating_bar = "█" * r["self_rating"] + "░" * (10 - r["self_rating"])
        cv_flag = "✓" if r["cv_claimed"] else "—"
        table_rows.append(f"""
    <tr style="background:{bg}">
      <td><strong>{h(r['skill'])}</strong></td>
      <td style="font-family:monospace;font-size:11px;">{rating_bar} {r['self_rating']}/10</td>
      <td style="text-align:center">{cv_flag}</td>
      <td>{demand_str}</td>
      <td style="color:{color};font-weight:600">{h(r['gap_level'].capitalize())}</td>
      <td style="font-size:12px">{h(r['recommendation'])}</td>
    </tr>""")

    # Summary callout for critical gaps
    critical = gap_data.get("critical", [])
    summary = ""
    if critical:
        names = ", ".join(r["skill"] for r in critical[:5])
        summary = f"""
<div style="background:#fff5f5;border-left:4px solid #d63031;padding:12px 16px;
            border-radius:0 6px 6px 0;margin-bottom:16px;font-size:13px;">
  <strong>Critical gaps requiring immediate attention:</strong> {h(names)}<br>
  These skills have high market demand but low current proficiency.
  Consider increasing weekly study hours.
</div>"""

    note = ""
    if not gap_data.get("job_demand"):
        note = """<p style="font-size:12px;color:#636e72;margin-top:10px;">
  ⚠ No live job demand data — run <code>python -m src.main collect-jobs</code>
  to fetch real posting counts from Bundesagentur / Indeed.</p>"""

    return summary + header + "\n".join(table_rows) + "\n  </tbody>\n</table>" + note


def render_gap_markdown(gap_data: Dict[str, Any]) -> str:
    """Render the gap analysis as a Markdown table."""
    rows = gap_data["rows"]
    if not rows:
        return "_No skill gap data. Run `collect-jobs` first._"

    lines = [
        "| Skill | Self (0–10) | On CV | Demand | Gap | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        rating = f"{r['self_rating']}/10"
        cv = "✓" if r["cv_claimed"] else "—"
        lines.append(
            f"| {r['skill']} | {rating} | {cv} | {r['demand']} ({r['demand_count']}) "
            f"| {r['gap_level'].capitalize()} | {r['recommendation']} |"
        )
    return "\n".join(lines)
