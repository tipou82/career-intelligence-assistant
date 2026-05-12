"""Company press release and newsroom monitor.

Strategy:
  - Companies with direct RSS feeds: fetched via collect_rss (sources.yaml).
  - Companies without RSS: tracked via Google News RSS search queries, which
    aggregate press releases, blog posts, and media coverage per company/topic.

This module manages the Google News RSS layer. Sources are defined in
config/pressreleases.yaml and injected into the normal collect pipeline.

Run:  python -m src.main collect-press
"""

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import feedparser
import yaml

from .database import init_db, insert_article

CONFIG_PATH = Path(__file__).parent.parent / "config" / "pressreleases.yaml"
MAX_ENTRIES = 50


def _build_gnews_url(query: str, lang: str = "en", country: str = "US") -> str:
    import urllib.parse
    q = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={country}&ceid={country}:{lang}"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def _parse_date(entry: Any) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6]).isoformat()
            except (ValueError, TypeError):
                pass
    return datetime.utcnow().isoformat()


def _fetch_source(source: Dict) -> List[Dict[str, Any]]:
    """Fetch one press source. Builds a Google News URL if no url given."""
    url = source.get("url") or _build_gnews_url(
        source["query"],
        lang=source.get("lang", "en"),
        country=source.get("country", "US"),
    )
    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        print(f"    [warn] {source.get('name', url)}: {exc}")
        return []

    articles = []
    for entry in feed.entries[:MAX_ENTRIES]:
        raw = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        articles.append({
            "title": getattr(entry, "title", "").strip(),
            "url": getattr(entry, "link", ""),
            "source_name": source["name"],
            "published_date": _parse_date(entry),
            "summary": _strip_html(raw)[:2000],
            "raw_content": "",
        })
    return articles


def collect_pressreleases(config_path: Path = CONFIG_PATH) -> Dict[str, int]:
    """Fetch press releases for all configured company/topic monitors.

    Returns stats dict: {fetched, new, skipped}.
    """
    init_db()

    if not config_path.exists():
        print(f"  [warn] {config_path} not found — skipping press release collection.")
        return {"fetched": 0, "new": 0, "skipped": 0}

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    stats: Dict[str, int] = {"fetched": 0, "new": 0, "skipped": 0}

    for source in config.get("sources", []):
        print(f"  Fetching: {source['name']} ...")
        articles = _fetch_source(source)
        stats["fetched"] += len(articles)
        for article in articles:
            row_id = insert_article(article)
            if row_id is not None:
                stats["new"] += 1
            else:
                stats["skipped"] += 1
        time.sleep(0.5)

    return stats
