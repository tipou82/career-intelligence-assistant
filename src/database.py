"""SQLite database layer — schema init, insert, update, and query helpers."""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "articles.sqlite"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


_JOB_AD_BACKFILL_SQL = """
UPDATE articles SET is_job_ad = 1
WHERE is_job_ad = 0 AND (
    url   LIKE '%stellenmarkt%'
    OR title LIKE '%(m/w/d)%'
    OR title LIKE '%(w/m/d)%'
    OR title LIKE '%(m/f/d)%'
    OR title LIKE '%(f/m/d)%'
    OR title LIKE '%Stellenausschreibung%'
    OR title LIKE '%Lehrauftrag%'
    OR title LIKE 'Anzeige: IT-Jobs%'
    OR source_name LIKE 'GNews StepStone%'
    OR source_name LIKE 'GNews Zeit Stellenmarkt%'
    OR source_name LIKE 'GNews nmz Stellenmarkt%'
    OR (title LIKE '%sucht%' AND (
        title LIKE '%Projektmanager%' OR title LIKE '%Leiter%'
        OR title LIKE '%Koordinator%' OR title LIKE '%Referent%'
        OR title LIKE '%Engineer%' OR title LIKE '%Ingenieur%'
        OR title LIKE '%Entwickler%' OR title LIKE '%Developer%'
        OR title LIKE '%Architekt%' OR title LIKE '%Consultant%'
    ))
    OR title LIKE '%schreibt%Stellen aus%'
    OR (url LIKE '%/jobs/%' AND source_name LIKE '%LinkedIn%')
    OR (url LIKE '%/jobs/%' AND source_name LIKE '%StepStone%')
    OR (url LIKE '%/jobs/%' AND source_name LIKE '%Indeed%')
);
"""


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables and indexes if they do not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        # Step 1: create tables
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                title             TEXT NOT NULL,
                url               TEXT UNIQUE,
                source_name       TEXT,
                language          TEXT DEFAULT 'en',
                published_date    TEXT,
                summary           TEXT,
                raw_content       TEXT,
                classification    TEXT,
                relevance_score   REAL DEFAULT 0.0,
                confidence_level  TEXT DEFAULT 'low',
                signal_strength   TEXT DEFAULT 'noise',
                recommended_action TEXT DEFAULT 'watch',
                career_actionability_score REAL DEFAULT 0.0,
                is_job_ad         INTEGER DEFAULT 0,
                classified_at     TEXT,
                created_at        TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                week_label  TEXT UNIQUE,
                filepath    TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        # Step 2: migrate existing databases — add new columns if absent
        existing = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
        if "language" not in existing:
            conn.execute("ALTER TABLE articles ADD COLUMN language TEXT DEFAULT 'en'")
        if "career_actionability_score" not in existing:
            conn.execute("ALTER TABLE articles ADD COLUMN career_actionability_score REAL DEFAULT 0.0")
        if "is_job_ad" not in existing:
            conn.execute("ALTER TABLE articles ADD COLUMN is_job_ad INTEGER DEFAULT 0")
        # Step 3: backfill is_job_ad for rows classified before this column existed
        conn.execute(_JOB_AD_BACKFILL_SQL)
        # Step 4: create indexes (after migration so language column is guaranteed present)
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_articles_published
                ON articles(published_date);
            CREATE INDEX IF NOT EXISTS idx_articles_score
                ON articles(relevance_score);
            CREATE INDEX IF NOT EXISTS idx_articles_signal
                ON articles(signal_strength);
            CREATE INDEX IF NOT EXISTS idx_articles_language
                ON articles(language);
            CREATE INDEX IF NOT EXISTS idx_articles_job_ad
                ON articles(is_job_ad);
        """)


def insert_article(article: Dict[str, Any], db_path: Path = DB_PATH) -> Optional[int]:
    """Insert article; silently skip if URL already exists. Returns new row id or None."""
    with get_connection(db_path) as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO articles
                   (title, url, source_name, language, published_date, summary, raw_content)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    article.get("title", ""),
                    article.get("url", ""),
                    article.get("source_name", ""),
                    article.get("language", "en"),
                    article.get("published_date", ""),
                    article.get("summary", ""),
                    article.get("raw_content", ""),
                ),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def update_article_classification(
    article_id: int,
    classification: Dict[str, Any],
    relevance_score: float,
    confidence_level: str,
    signal_strength: str,
    recommended_action: str,
    career_actionability_score: float = 0.0,
    is_job_ad: bool = False,
    db_path: Path = DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """UPDATE articles SET
               classification             = ?,
               relevance_score            = ?,
               career_actionability_score = ?,
               confidence_level           = ?,
               signal_strength            = ?,
               recommended_action         = ?,
               is_job_ad                  = ?,
               classified_at              = datetime('now')
               WHERE id = ?""",
            (
                json.dumps(classification),
                round(relevance_score, 2),
                round(career_actionability_score, 2),
                confidence_level,
                signal_strength,
                recommended_action,
                1 if is_job_ad else 0,
                article_id,
            ),
        )


def get_unclassified_articles(db_path: Path = DB_PATH) -> List[Dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE classified_at IS NULL ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_articles_for_week(week_label: str, db_path: Path = DB_PATH) -> List[Dict]:
    """Return articles whose published_date falls in the given ISO week (YYYY-WW)."""
    year, week = map(int, week_label.split("-"))
    # Derive Monday of the target ISO week from Jan 4 (always in week 1)
    jan4 = date(year, 1, 4)
    week1_monday = jan4 - timedelta(days=jan4.weekday())
    week_start = week1_monday + timedelta(weeks=week - 1)
    week_end = week_start + timedelta(days=6)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE date(published_date) BETWEEN ? AND ?
               ORDER BY relevance_score DESC""",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_articles(db_path: Path = DB_PATH) -> List[Dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY relevance_score DESC, published_date DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def save_report(week_label: str, filepath: str, db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reports (week_label, filepath) VALUES (?, ?)",
            (week_label, filepath),
        )


def get_job_ads(min_score: float = 6.0, db_path: Path = DB_PATH) -> List[Dict]:
    """Return all job-ad articles with relevance_score >= min_score, newest first."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE is_job_ad = 1 AND relevance_score >= ?
               ORDER BY relevance_score DESC, published_date DESC""",
            (min_score,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats(db_path: Path = DB_PATH) -> Dict[str, int]:
    with get_connection(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        classified = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE classified_at IS NOT NULL"
        ).fetchone()[0]
        strong = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE signal_strength = 'strong'"
        ).fetchone()[0]
    return {"total": total, "classified": classified, "strong": strong}
