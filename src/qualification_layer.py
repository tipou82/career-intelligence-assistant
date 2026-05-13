"""Qualification layer — targeted qualification recommendations for a specific person.

Loads config/qualification_actions.yaml, scores each action, classifies into
must_have / high_roi / nice_to_have / avoid_for_now, and builds report sections.

Scoring formula (all inputs 0.0–1.0):
    qualification_score =
        market_frequency_score * 0.30
      + target_role_relevance  * 0.25
      + profile_gap_score      * 0.20
      + evidence_output_score  * 0.15
      + feasibility_score      * 0.10
      - cost_time_penalty      * 0.10

Categories by score threshold (overrideable per action):
    >= 0.72  must_have
    >= 0.52  high_roi
    >= 0.35  nice_to_have
    <  0.35  avoid_for_now

Run standalone:
    python -m src.main qualifications
"""

import html as html_lib
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config" / "qualification_actions.yaml"

# Score thresholds for automatic category assignment
THRESHOLDS = {
    "must_have": 0.72,
    "high_roi":  0.52,
    "nice_to_have": 0.35,
}

CATEGORY_ORDER = ["must_have", "high_roi", "nice_to_have", "avoid_for_now"]

CATEGORY_LABELS = {
    "must_have":    "Must-Have",
    "high_roi":     "High-ROI",
    "nice_to_have": "Nice-to-Have",
    "avoid_for_now": "Avoid for Now",
}

WEIGHTS = {
    "market_frequency":    0.30,
    "target_role_relevance": 0.25,
    "profile_gap":         0.20,
    "evidence_output":     0.15,
    "feasibility":         0.10,
    "cost_time_penalty":  -0.10,   # penalty — subtracted
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def compute_qualification_score(action: Dict[str, Any]) -> float:
    """Compute the qualification_score for one action.

    All input scores are expected in the 0.0–1.0 range.
    Returns a clamped 0.0–1.0 float.
    """
    s = action.get("scores", {})
    score = (
        s.get("market_frequency", 0.5)      * WEIGHTS["market_frequency"]
        + s.get("target_role_relevance", 0.5) * WEIGHTS["target_role_relevance"]
        + s.get("profile_gap", 0.5)           * WEIGHTS["profile_gap"]
        + s.get("evidence_output", 0.5)       * WEIGHTS["evidence_output"]
        + s.get("feasibility", 0.5)           * WEIGHTS["feasibility"]
        + s.get("cost_time_penalty", 0.0)     * WEIGHTS["cost_time_penalty"]
    )
    return round(min(max(score, 0.0), 1.0), 3)


def classify_action(action: Dict[str, Any], score: float) -> str:
    """Return the category for an action.

    Respects override_category if set to a valid category name.
    """
    override = action.get("override_category")
    if override in CATEGORY_ORDER:
        return override
    if score >= THRESHOLDS["must_have"]:
        return "must_have"
    if score >= THRESHOLDS["high_roi"]:
        return "high_roi"
    if score >= THRESHOLDS["nice_to_have"]:
        return "nice_to_have"
    return "avoid_for_now"


# ---------------------------------------------------------------------------
# Load and score
# ---------------------------------------------------------------------------

def load_and_score(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Load qualification_actions.yaml, score every action, and group by category.

    Returns a dict:
        strategy        — qualification_strategy block
        scored_actions  — flat list, sorted by score desc
        by_category     — dict[category] → list of actions
    """
    if not config_path.exists():
        return {"strategy": {}, "scored_actions": [], "by_category": {c: [] for c in CATEGORY_ORDER}}

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    strategy = data.get("qualification_strategy", {})
    raw_actions = data.get("qualification_actions", [])

    scored: List[Dict] = []
    for action in raw_actions:
        score = compute_qualification_score(action)
        category = classify_action(action, score)
        scored.append({**action, "_score": score, "_category": category})

    scored.sort(key=lambda a: a["_score"], reverse=True)

    by_category: Dict[str, List] = {c: [] for c in CATEGORY_ORDER}
    for action in scored:
        by_category[action["_category"]].append(action)

    return {
        "strategy": strategy,
        "scored_actions": scored,
        "by_category": by_category,
    }


# ---------------------------------------------------------------------------
# Anti-patterns check
# ---------------------------------------------------------------------------

_VAGUE_ACTIONS = frozenset([
    "learn ai", "improve communication", "study more", "take a course",
    "get better at", "develop skills", "learn programming", "study german",
])


def _check_guardrails(strategy: Dict, by_category: Dict) -> List[str]:
    """Return a list of warning messages if guardrail violations are detected."""
    warnings = []
    cap = strategy.get("weekly_hours_cap", 8)
    limits = {
        "must_have": 2,
        "high_roi": 3,
        "nice_to_have": 2,
        "avoid_for_now": 3,
    }
    for cat, limit in limits.items():
        actions = by_category.get(cat, [])
        if len(actions) > limit:
            warnings.append(
                f"⚠️ {len(actions)} {CATEGORY_LABELS[cat]} items — "
                f"cap is {limit}. Lower-scoring items may be noise."
            )
    must_hours = sum(a.get("estimated_weekly_hours", 0) for a in by_category.get("must_have", []))
    if must_hours > cap:
        warnings.append(
            f"⚠️ Must-have items alone require {must_hours} h/week — "
            f"exceeds cap of {cap} h. Prioritise ruthlessly."
        )
    return warnings


# ---------------------------------------------------------------------------
# Markdown section builder
# ---------------------------------------------------------------------------

def build_qualification_md(data: Dict[str, Any]) -> str:
    """Build the Markdown section for insertion into the weekly report."""
    strategy = data.get("strategy", {})
    by_category = data.get("by_category", {c: [] for c in CATEGORY_ORDER})

    person = strategy.get("target_person", "N/A")
    cap = strategy.get("weekly_hours_cap", 8)

    warnings = _check_guardrails(strategy, by_category)

    lines: List[str] = [
        f"_Target person: **{person}** · Weekly time budget: **{cap} h**_\n",
    ]

    if warnings:
        for w in warnings:
            lines.append(f"> {w}\n")

    # ── Must-have and High-ROI — full table ──────────────────────────────
    for cat in ("must_have", "high_roi"):
        actions = by_category.get(cat, [])
        if not actions:
            continue
        label = CATEGORY_LABELS[cat]
        lines.append(f"\n### {label}\n")
        lines.append("| Qualification | Why it matters | Action | Time | Visible evidence |")
        lines.append("|---|---|---|---|---|")
        for a in actions:
            name = a.get("name", "—")
            why = a.get("target_role_relevance_note", a.get("profile_gap_addressed", "—"))
            action_text = a.get("recommended_action", "—").replace("\n", " ").strip()
            time_h = a.get("estimated_weekly_hours", "?")
            cost = a.get("estimated_cost_eur")
            time_str = f"{time_h} h/wk" + (f" · €{cost}" if cost else "")
            evidence = a.get("expected_visible_output", "—")
            lines.append(f"| **{name}** | {why} | {action_text} | {time_str} | {evidence} |")

    # ── Nice-to-have — condensed ─────────────────────────────────────────
    actions = by_category.get("nice_to_have", [])
    if actions:
        lines.append(f"\n### {CATEGORY_LABELS['nice_to_have']}\n")
        lines.append("| Qualification | Why not urgent | Later action |")
        lines.append("|---|---|---|")
        for a in actions:
            name = a.get("name", "—")
            deferral = a.get("reason_for_deferral_if_any") or "Not urgent for immediate applications"
            later = a.get("recommended_action", "—").split(".")[0].strip()
            lines.append(f"| {name} | {deferral} | {later} |")

    # ── Avoid for now — list only ────────────────────────────────────────
    actions = by_category.get("avoid_for_now", [])
    if actions:
        lines.append(f"\n### {CATEGORY_LABELS['avoid_for_now']}\n")
        lines.append("| Qualification | Why to avoid / defer |")
        lines.append("|---|---|")
        for a in actions:
            name = a.get("name", "—")
            deferral = a.get("reason_for_deferral_if_any") or "Low return relative to time and cost"
            lines.append(f"| {name} | {deferral} |")

    # ── Principle reminder ───────────────────────────────────────────────
    principle = strategy.get("principle", "")
    if principle:
        principle_line = principle.replace("\n", " ").strip()[:200]
        lines.append(f"\n> **Principle:** _{principle_line}_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML section builder
# ---------------------------------------------------------------------------

def _h(text: str) -> str:
    return html_lib.escape(str(text))


def build_qualification_html(data: Dict[str, Any]) -> str:
    """Build an HTML section for embedding in the HTML report."""
    strategy = data.get("strategy", {})
    by_category = data.get("by_category", {c: [] for c in CATEGORY_ORDER})

    person = _h(strategy.get("target_person", "N/A"))
    cap = strategy.get("weekly_hours_cap", 8)
    warnings = _check_guardrails(strategy, by_category)

    cat_colors = {
        "must_have": ("#d63031", "#fff5f5"),
        "high_roi":  ("#00b894", "#f0fdf4"),
        "nice_to_have": ("#fdcb6e", "#fffaf0"),
        "avoid_for_now": ("#636e72", "#f8f9fa"),
    }

    html_parts = [
        f'<p style="font-size:13px;color:#636e72">'
        f'Target person: <strong>{person}</strong> · '
        f'Weekly time budget: <strong>{cap} h</strong></p>'
    ]

    for w in warnings:
        html_parts.append(
            f'<p style="color:#e17055;font-size:12px">⚠ {_h(w)}</p>'
        )

    for cat in CATEGORY_ORDER:
        actions = by_category.get(cat, [])
        if not actions:
            continue
        label = CATEGORY_LABELS[cat]
        border_color, bg_color = cat_colors[cat]

        html_parts.append(
            f'<div style="margin-bottom:18px;">'
            f'<h4 style="border-left:4px solid {border_color};padding-left:10px;'
            f'margin:0 0 10px;color:{border_color}">{label}</h4>'
        )

        if cat in ("must_have", "high_roi"):
            html_parts.append(
                '<table><thead><tr>'
                '<th>Qualification</th><th>Why it matters</th>'
                '<th>Action</th><th>Time</th><th>Visible evidence</th>'
                '</tr></thead><tbody>'
            )
            for a in actions:
                name = _h(a.get("name", "—"))
                why = _h(a.get("target_role_relevance_note", a.get("profile_gap_addressed", "—")))
                action_text = _h(a.get("recommended_action", "—").replace("\n", " ").strip()[:150])
                time_h = a.get("estimated_weekly_hours", "?")
                cost = a.get("estimated_cost_eur")
                time_str = _h(f"{time_h} h/wk" + (f" · €{cost}" if cost else ""))
                evidence = _h(a.get("expected_visible_output", "—")[:80])
                score = a.get("_score", 0)
                score_badge = f'<span style="font-size:10px;color:#999">{score:.2f}</span>'
                html_parts.append(
                    f'<tr style="background:{bg_color}">'
                    f'<td><strong>{name}</strong> {score_badge}</td>'
                    f'<td style="font-size:12px">{why}</td>'
                    f'<td style="font-size:12px">{action_text}</td>'
                    f'<td style="font-size:12px;white-space:nowrap">{time_str}</td>'
                    f'<td style="font-size:12px">{evidence}</td>'
                    f'</tr>'
                )
            html_parts.append('</tbody></table>')

        elif cat == "nice_to_have":
            html_parts.append(
                '<table><thead><tr>'
                '<th>Qualification</th><th>Why not urgent</th><th>Later action</th>'
                '</tr></thead><tbody>'
            )
            for a in actions:
                name = _h(a.get("name", "—"))
                deferral = _h(
                    a.get("reason_for_deferral_if_any") or "Not urgent for immediate applications"
                )
                later = _h(a.get("recommended_action", "—").split(".")[0].strip())
                html_parts.append(
                    f'<tr><td>{name}</td>'
                    f'<td style="font-size:12px;color:#636e72">{deferral}</td>'
                    f'<td style="font-size:12px">{later}</td></tr>'
                )
            html_parts.append('</tbody></table>')

        else:  # avoid_for_now
            html_parts.append(
                '<table><thead><tr>'
                '<th>Qualification</th><th>Why to avoid / defer</th>'
                '</tr></thead><tbody>'
            )
            for a in actions:
                name = _h(a.get("name", "—"))
                deferral = _h(
                    a.get("reason_for_deferral_if_any") or "Low return relative to time and cost"
                )
                html_parts.append(
                    f'<tr><td style="color:#636e72">{name}</td>'
                    f'<td style="font-size:12px;color:#636e72">{deferral}</td></tr>'
                )
            html_parts.append('</tbody></table>')

        html_parts.append('</div>')

    principle = strategy.get("principle", "")
    if principle:
        p = _h(principle.replace("\n", " ").strip()[:250])
        html_parts.append(
            f'<p style="font-size:11px;color:#636e72;border-top:1px solid #e8eaf0;'
            f'padding-top:8px;margin-top:12px;"><em>Principle: {p}</em></p>'
        )

    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# Standalone CLI output
# ---------------------------------------------------------------------------

def print_qualification_report() -> None:
    """Print a standalone qualification report to stdout."""
    data = load_and_score()
    strategy = data["strategy"]
    person = strategy.get("target_person", "N/A")
    cap = strategy.get("weekly_hours_cap", 8)

    print("=" * 65)
    print(f"  Qualification Actions — {person}  (cap: {cap} h/week)")
    print("=" * 65)

    by_category = data["by_category"]
    warnings = _check_guardrails(strategy, by_category)
    for w in warnings:
        print(f"  {w}")
    if warnings:
        print()

    for cat in CATEGORY_ORDER:
        actions = by_category.get(cat, [])
        if not actions:
            continue
        label = CATEGORY_LABELS[cat]
        print(f"\n── {label} {'─' * (60 - len(label) - 4)}")
        for a in actions:
            name = a.get("name", "—")
            score = a["_score"]
            time_h = a.get("estimated_weekly_hours", "?")
            cost = a.get("estimated_cost_eur")
            cost_str = f" · €{cost}" if cost else ""
            action_text = a.get("recommended_action", "—").replace("\n", " ").strip()[:100]
            print(f"  [{score:.2f}] {name}  ({time_h} h/wk{cost_str})")
            print(f"         → {action_text}")
    print()
