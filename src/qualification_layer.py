"""Qualification layer — targeted qualification recommendations with market-signal enrichment.

Static scoring (config/qualification_actions.yaml) is enriched weekly by:
  1. job_signals table  — posting counts for keywords from collect-jobs
  2. articles table     — how often related topics appear in this week's signals

Dynamic market_frequency replaces the static value when market data is available:
  blended = 0.5 x dynamic_signal_score  +  0.5 x static_expert_score

This ensures the report responds to actual market conditions rather than showing
the same scores every week.

Scoring formula (all inputs 0.0-1.0):
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
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
# Market signal enrichment
# ---------------------------------------------------------------------------

def _current_week() -> str:
    d = date.today()
    y, w, _ = d.isocalendar()
    return f"{y}-{w:02d}"


def _build_job_index(week_label: str) -> Dict[str, int]:
    """Return {lowercased_keyword: total_posting_count} from job_signals for the week."""
    try:
        from .database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT query, skill_tags, result_count FROM job_signals WHERE week_label = ?",
                (week_label,),
            ).fetchall()
    except Exception:
        return {}
    index: Dict[str, int] = {}
    for query, skill_tags, count in rows:
        count = int(count or 0)
        # Index each word in the query
        for word in (query or "").lower().split():
            index[word] = index.get(word, 0) + count
        # Index the full query phrase
        q = (query or "").lower().strip()
        if q:
            index[q] = index.get(q, 0) + count
        # Index skill_tags as individual entries
        for tag in (skill_tags or "").split(","):
            t = tag.strip().lower()
            if t:
                index[t] = index.get(t, 0) + count
    return index


def _build_article_index(days_back: int = 14) -> Dict[str, int]:
    """Return {lowercased_term: article_count} from classified articles in recent days."""
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    try:
        from .database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT classification FROM articles
                   WHERE date(published_date) >= ?
                     AND signal_strength IN ('strong', 'weak')
                     AND classified_at IS NOT NULL""",
                (cutoff,),
            ).fetchall()
    except Exception:
        return {}
    index: Dict[str, int] = {}
    for (cls_json,) in rows:
        try:
            cls = json.loads(cls_json) if cls_json else {}
        except (json.JSONDecodeError, TypeError):
            continue
        terms = cls.get("technologies", []) + cls.get("skills", [])
        for t in terms:
            key = t.lower().strip()
            if key:
                index[key] = index.get(key, 0) + 1
    return index


def _match_count(keywords: List[str], index: Dict[str, int]) -> int:
    """Sum index counts for keywords (exact match first, then substring)."""
    total = 0
    counted: set = set()
    for kw in keywords:
        kl = kw.lower().strip()
        if not kl:
            continue
        if kl in index:
            total += index[kl]
            counted.add(kl)
        else:
            # Substring: find first index key that contains this keyword
            for k, v in index.items():
                if kl in k and k not in counted:
                    total += v
                    counted.add(k)
                    break
    return total


def _blend_frequency(static: float, job_count: int, art_count: int) -> Tuple[float, str]:
    """Blend static expert score with live market signal counts.

    Returns (blended_score, display_note).
    No data → returns static unchanged.
    """
    if job_count == 0 and art_count == 0:
        return static, ""

    # Normalize: log scale, 100 job postings or 20 articles → signal_score = 1.0
    job_freq = min(math.log1p(job_count) / math.log1p(100), 1.0) if job_count > 0 else 0.0
    art_freq = min(math.log1p(art_count) / math.log1p(20), 1.0)  if art_count > 0 else 0.0

    if job_count > 0 and art_count > 0:
        dynamic = 0.6 * job_freq + 0.4 * art_freq
    elif job_count > 0:
        dynamic = job_freq
    else:
        dynamic = 0.7 * art_freq  # articles alone carry less weight

    blended = round(0.5 * dynamic + 0.5 * static, 3)

    parts = []
    if job_count > 0:
        parts.append(f"{job_count} job postings")
    if art_count > 0:
        parts.append(f"{art_count} article signals")
    note = "Market signals this week: " + ", ".join(parts)

    return blended, note


def enrich_scores_from_market(
    data: Dict[str, Any],
    week_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Dynamically adjust market_frequency scores based on current week's signals.

    Reads job_signals (from collect-jobs) and recent articles (from classify)
    to compute a live market_frequency for each qualification action.

    The blended score replaces the static score only when market data is found.
    The original static score is preserved in _market_freq_was for transparency.
    """
    if week_label is None:
        week_label = _current_week()

    job_index = _build_job_index(week_label)
    art_index = _build_article_index(days_back=14)

    if not job_index and not art_index:
        # No data at all — return unchanged, add note
        return {**data, "_enriched": False, "_week_label": week_label,
                "_enrichment_note": "No market data found — run collect-jobs first."}

    enriched: List[Dict] = []
    for action in data.get("scored_actions", []):
        kw_block = action.get("market_signal_keywords", {})
        job_kws = kw_block.get("job_signals", [])
        art_kws = kw_block.get("articles", [])

        job_count = _match_count(job_kws, job_index)
        art_count = _match_count(art_kws, art_index)

        if job_count > 0 or art_count > 0:
            static_freq = action.get("scores", {}).get("market_frequency", 0.5)
            blended, note = _blend_frequency(static_freq, job_count, art_count)

            updated_scores = {**action.get("scores", {}), "market_frequency": blended}
            new_score = compute_qualification_score({**action, "scores": updated_scores})
            new_cat = classify_action(action, new_score)

            enriched.append({
                **action,
                "scores": updated_scores,
                "_score": new_score,
                "_category": new_cat,
                "_market_job_count": job_count,
                "_market_art_count": art_count,
                "_market_freq_was": static_freq,
                "_market_freq_now": blended,
                "_market_note": note,
            })
        else:
            enriched.append(action)

    enriched.sort(key=lambda a: a["_score"], reverse=True)
    by_category: Dict[str, List] = {c: [] for c in CATEGORY_ORDER}
    for a in enriched:
        by_category[a["_category"]].append(a)

    adjusted = sum(1 for a in enriched if "_market_note" in a)
    return {
        **data,
        "scored_actions": enriched,
        "by_category": by_category,
        "_enriched": True,
        "_week_label": week_label,
        "_enrichment_note": f"Market signals applied to {adjusted}/{len(enriched)} actions this week.",
    }


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

    base = {
        "strategy": strategy,
        "scored_actions": scored,
        "by_category": by_category,
    }

    # Enrich with live market signals (silently skips if no data)
    return enrich_scores_from_market(base)


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

def _market_badge_md(action: Dict) -> str:
    """Return a short market-signal badge for Markdown."""
    jc = action.get("_market_job_count", 0)
    ac = action.get("_market_art_count", 0)
    was = action.get("_market_freq_was")
    now = action.get("_market_freq_now")
    if was is None:
        return ""
    direction = "↑" if now > was else ("↓" if now < was else "→")
    parts = []
    if jc > 0:
        parts.append(f"{jc} job postings")
    if ac > 0:
        parts.append(f"{ac} articles")
    return f" `{direction} market: {', '.join(parts)}`" if parts else ""


def build_qualification_md(data: Dict[str, Any]) -> str:
    """Build the Markdown section for insertion into the weekly report."""
    strategy = data.get("strategy", {})
    by_category = data.get("by_category", {c: [] for c in CATEGORY_ORDER})

    person = strategy.get("target_person", "N/A")
    cap = strategy.get("weekly_hours_cap", 8)
    enrichment_note = data.get("_enrichment_note", "")

    warnings = _check_guardrails(strategy, by_category)

    lines: List[str] = [
        f"_Target person: **{person}** · Weekly time budget: **{cap} h**_\n",
    ]
    if enrichment_note:
        lines.append(f"_🔄 {enrichment_note}_\n")

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
            name = a.get("name", "—") + _market_badge_md(a)
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

    enrichment_note = data.get("_enrichment_note", "")
    if enrichment_note:
        icon = "🔄" if data.get("_enriched") else "⚠"
        html_parts.append(
            f'<p style="font-size:11px;color:#00b894;margin-bottom:10px">'
            f'{icon} {_h(enrichment_note)}</p>'
        )

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
                # Market signal badge
                jc = a.get("_market_job_count", 0)
                ac = a.get("_market_art_count", 0)
                was = a.get("_market_freq_was")
                market_badge = ""
                if was is not None and (jc > 0 or ac > 0):
                    direction = "↑" if a.get("_market_freq_now", was) > was else "↓"
                    parts = []
                    if jc > 0: parts.append(f"{jc} jobs")
                    if ac > 0: parts.append(f"{ac} articles")
                    market_badge = (
                        f' <span style="font-size:10px;background:#00b89420;color:#00745e;'
                        f'padding:1px 5px;border-radius:8px">'
                        f'{direction} {", ".join(parts)}</span>'
                    )
                html_parts.append(
                    f'<tr style="background:{bg_color}">'
                    f'<td><strong>{name}</strong> {score_badge}{market_badge}</td>'
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
