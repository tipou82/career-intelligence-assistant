"""Job market signal collector.

Sources:
  - Bundesagentur für Arbeit REST API (Germany, no auth required)
  - Indeed RSS feeds (global, best-effort — may be blocked in some regions)

Run:  python -m src.main collect-jobs
Results are stored in the `job_signals` table and surfaced in the weekly report.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .database import get_connection, init_db

CONFIG_PATH = Path(__file__).parent.parent / "config" / "jobs.yaml"

# Bundesagentur API endpoint (public, no auth)
_BA_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
_BA_HEADERS = {"X-API-Key": "jobboerse-jobsuche"}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _ensure_jobs_table() -> None:
    """Create job_signals table if it does not exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS job_signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                query        TEXT,
                region       TEXT,
                source       TEXT,
                result_count INTEGER DEFAULT 0,
                skill_tags   TEXT,
                fetched_at   TEXT DEFAULT (datetime('now')),
                week_label   TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_week
                ON job_signals(week_label);
        """)


def _current_week() -> str:
    from datetime import date
    d = date.today()
    year, week, _ = d.isocalendar()
    return f"{year}-{week:02d}"


def _save_job_signal(
    query: str,
    region: str,
    source: str,
    result_count: int,
    skill_tags: List[str],
) -> None:
    week = _current_week()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO job_signals (query, region, source, result_count, skill_tags, week_label)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (query, region, source, result_count, ",".join(skill_tags), week),
        )


# ---------------------------------------------------------------------------
# Bundesagentur collector
# ---------------------------------------------------------------------------

def _fetch_bundesagentur(query: str) -> int:
    """Return posting count for a query from Bundesagentur API."""
    try:
        import urllib.request
        import urllib.parse
        import json

        params = urllib.parse.urlencode({
            "was": query,
            "wo": "Deutschland",
            "page": 1,
            "size": 1,
        })
        url = f"{_BA_URL}?{params}"
        req = urllib.request.Request(url, headers=_BA_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return int(data.get("maxErgebnisse", 0))
    except Exception as exc:
        print(f"    [warn] Bundesagentur API error for '{query}': {exc}")
        return -1


# ---------------------------------------------------------------------------
# Indeed RSS collector
# ---------------------------------------------------------------------------

def _fetch_indeed_rss(query: str) -> int:
    """Return approximate job count from Indeed RSS (best-effort)."""
    try:
        import feedparser
        import urllib.parse

        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.indeed.com/rss?q={encoded}&sort=date"
        feed = feedparser.parse(url)
        if feed.get("status") in (200, 301, 302):
            return len(feed.entries)
        return 0
    except Exception as exc:
        print(f"    [warn] Indeed RSS error for '{query}': {exc}")
        return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collect_jobs(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Fetch job market signals for all configured queries.

    Returns stats dict: {searched, saved, errors}.
    """
    init_db()
    _ensure_jobs_table()

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    searches = config.get("searches", [])
    stats: Dict[str, int] = {"searched": 0, "saved": 0, "errors": 0}

    for search in searches:
        query = search["query"]
        source = search.get("source", "indeed_rss")
        region = search.get("region", "global")
        skill_tags = search.get("skill_tags", [])

        print(f"  [{source}] {query!r} ({region}) ...", end=" ", flush=True)

        if source == "bundesagentur":
            count = _fetch_bundesagentur(query)
        else:
            count = _fetch_indeed_rss(query)

        stats["searched"] += 1
        if count >= 0:
            _save_job_signal(query, region, source, count, skill_tags)
            stats["saved"] += 1
            print(f"{count} postings")
        else:
            stats["errors"] += 1
            print("error")

        time.sleep(0.5)

    return stats


def get_job_trends(week_label: str | None = None) -> List[Dict[str, Any]]:
    """Return job signal rows for the given week (defaults to current)."""
    _ensure_jobs_table()
    if week_label is None:
        week_label = _current_week()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM job_signals WHERE week_label = ? ORDER BY result_count DESC",
            (week_label,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_job_trends_summary(week_label: str | None = None) -> Dict[str, int]:
    """Aggregate skill tag counts from job signals for the week.

    Returns a dict mapping skill tag → total posting count.
    """
    rows = get_job_trends(week_label)
    totals: Dict[str, int] = {}
    for row in rows:
        if row["result_count"] <= 0:
            continue
        for tag in (row.get("skill_tags") or "").split(","):
            tag = tag.strip()
            if tag:
                totals[tag] = totals.get(tag, 0) + row["result_count"]
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))
