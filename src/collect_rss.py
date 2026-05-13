"""RSS feed collector — fetches feeds and stores new articles in the database."""

import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import feedparser
import yaml

from .database import init_db, insert_article

CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"
MAX_ENTRIES_PER_FEED = 50
FEED_TIMEOUT_SECONDS = 15  # per-feed HTTP timeout; skips slow/hanging feeds


class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    """Extend urllib's redirect handler to also follow HTTP 308 (Permanent Redirect).

    urllib handles 301/302/303/307 by default but silently fails on 308,
    which some feeds (e.g. VentureBeat) use. Treat 308 the same as 302.
    """
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)


_URL_OPENER = urllib.request.build_opener(_RedirectHandler())


def load_sources(config_path: Path = CONFIG_PATH) -> List[Dict]:
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("feeds", [])


def _parse_date(entry: Any) -> str:
    """Extract the best available date from a feed entry as an ISO string."""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6]).isoformat()
            except (ValueError, TypeError):
                pass
    return datetime.utcnow().isoformat()


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def fetch_feed(source: Dict) -> List[Dict[str, Any]]:
    """Fetch and parse one RSS source. Returns a list of article dicts.

    Uses a hard HTTP timeout so a slow server never blocks the whole pipeline.
    """
    url = source["url"]
    name = source.get("name", url)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "career-intelligence-assistant/1.0 (feedparser)"},
        )
        with _URL_OPENER.open(req, timeout=FEED_TIMEOUT_SECONDS) as resp:
            raw_bytes = resp.read()
        feed = feedparser.parse(raw_bytes)
    except Exception as exc:
        print(f"    [warn] Skipped {name}: {exc}")
        return []

    articles: List[Dict[str, Any]] = []
    for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
        raw_summary = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        summary = _strip_html(raw_summary)[:2000]
        articles.append(
            {
                "title": getattr(entry, "title", "").strip(),
                "url": getattr(entry, "link", ""),
                "source_name": source.get(
                    "name", getattr(feed.feed, "title", "Unknown")
                ),
                "language": source.get("language", "en"),
                "published_date": _parse_date(entry),
                "summary": summary,
                "raw_content": "",
            }
        )
    return articles


def collect_all(config_path: Path = CONFIG_PATH) -> Dict[str, int]:
    """Collect articles from all configured RSS sources.

    Returns a stats dict with keys: fetched, new, skipped.
    """
    init_db()
    sources = load_sources(config_path)
    stats: Dict[str, int] = {"fetched": 0, "new": 0, "skipped": 0}

    for source in sources:
        print(f"  Fetching: {source.get('name', source['url'])} ...")
        articles = fetch_feed(source)
        stats["fetched"] += len(articles)
        for article in articles:
            row_id = insert_article(article)
            if row_id is not None:
                stats["new"] += 1
            else:
                stats["skipped"] += 1
        time.sleep(0.5)  # polite delay between requests

    return stats
