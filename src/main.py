"""CLI entry point.

Usage:
    python -m src.main collect               # RSS feeds
    python -m src.main collect-press         # Company newsrooms + Google News
    python -m src.main collect-jobs          # Bundesagentur + Indeed job signals
    python -m src.main classify              # Rule-based classifier
    python -m src.main classify --llm openai # OpenAI classifier
    python -m src.main classify --llm claude # Anthropic Claude classifier
    python -m src.main report                # Generate Markdown + HTML report
    python -m src.main report --week 2026-19 --format html
    python -m src.main skill-gap             # Print skill gap analysis to console
    python -m src.main send-email            # Send HTML report via SMTP
    python -m src.main send-email --week 2026-19
    python -m src.main run-weekly            # Full pipeline (all steps)
    python -m src.main status                # Database statistics
"""

import argparse
import sys


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_collect(args: argparse.Namespace) -> None:
    from .collect_rss import collect_all
    print("Collecting RSS feeds...")
    stats = collect_all()
    print(
        f"  Done.  Fetched: {stats['fetched']}  |  "
        f"New: {stats['new']}  |  Duplicates skipped: {stats['skipped']}"
    )


def cmd_collect_press(args: argparse.Namespace) -> None:
    from .collect_pressreleases import collect_pressreleases
    print("Collecting company press releases and newsroom feeds...")
    stats = collect_pressreleases()
    print(
        f"  Done.  Fetched: {stats['fetched']}  |  "
        f"New: {stats['new']}  |  Duplicates skipped: {stats['skipped']}"
    )


def cmd_collect_jobs(args: argparse.Namespace) -> None:
    from .collect_jobs import collect_jobs
    print("Collecting job market signals...")
    stats = collect_jobs()
    print(
        f"  Done.  Searched: {stats['searched']}  |  "
        f"Saved: {stats['saved']}  |  Errors: {stats['errors']}"
    )


def cmd_classify(args: argparse.Namespace) -> None:
    llm = getattr(args, "llm", None)
    llm_classifier = None

    if llm == "claude":
        from .llm_classifier import AnthropicClassifier
        print("Classifying articles with Claude (claude-haiku-4-5)...")
        llm_classifier = AnthropicClassifier()
    elif llm == "openai":
        from .llm_classifier import OpenAIClassifier
        print("Classifying articles with OpenAI...")
        llm_classifier = OpenAIClassifier()
    else:
        print("Classifying articles (rule-based)...")

    from .classify_articles import classify_all
    stats = classify_all(llm_classifier=llm_classifier)
    print(f"  Done.  Classified: {stats['classified']}")


def cmd_report(args: argparse.Namespace) -> None:
    from .generate_weekly_report import generate_report
    from .skill_gap import analyse_skill_gap, render_gap_html

    week = getattr(args, "week", "current")
    fmt = getattr(args, "format", "both")

    print(f"Analysing skill gap...")
    gap_data = analyse_skill_gap()
    gap_html = render_gap_html(gap_data)

    print(f"Generating report (week={week}, format={fmt})...")
    saved = generate_report(week_label=week, fmt=fmt, skill_gap_html=gap_html)

    for fmt_key, path in saved.items():
        print(f"  Saved [{fmt_key.upper()}]: {path}")


def cmd_skill_gap(args: argparse.Namespace) -> None:
    from .skill_gap import analyse_skill_gap, render_gap_markdown
    print("Skill Gap Analysis\n" + "=" * 50)
    gap_data = analyse_skill_gap()
    print(render_gap_markdown(gap_data))

    if gap_data["critical"]:
        print("\nCritical gaps (high demand, low proficiency):")
        for r in gap_data["critical"]:
            print(f"  • {r['skill']}: {r['recommendation']}")


def cmd_send_email(args: argparse.Namespace) -> None:
    from pathlib import Path
    from .generate_weekly_report import get_week_label
    from .email_digest import send_report

    week = getattr(args, "week", "current")
    week_label = get_week_label(week)

    reports_dir = Path(__file__).parent.parent / "reports"
    html_path = reports_dir / f"weekly_career_brief_{week_label}.html"
    md_path = reports_dir / f"weekly_career_brief_{week_label}.md"

    if not html_path.exists():
        print(f"  HTML report not found: {html_path}")
        print(f"  Run: python -m src.main report --week {week} first.")
        sys.exit(1)

    print(f"Sending email digest for week {week_label}...")
    ok = send_report(html_path, week_label, md_path=md_path if md_path.exists() else None)
    if not ok:
        sys.exit(1)


def cmd_run_weekly(args: argparse.Namespace) -> None:
    print("=" * 60)
    print("  Career Intelligence Assistant – Weekly Pipeline")
    print("=" * 60)

    cmd_collect(args)
    cmd_collect_press(args)
    cmd_collect_jobs(args)
    cmd_classify(args)
    cmd_report(args)

    # Auto-send email if configured
    from .email_digest import _load_config as _email_cfg
    cfg = _email_cfg()
    if cfg.get("enabled", False):
        cmd_send_email(args)

    print("=" * 60)
    print("  Weekly run complete.")
    print("=" * 60)


def cmd_status(args: argparse.Namespace) -> None:
    from .database import get_stats, init_db
    from .collect_jobs import get_job_trends_summary

    init_db()
    stats = get_stats()
    print("Database status:")
    print(f"  Total articles   : {stats['total']}")
    print(f"  Classified       : {stats['classified']}")
    print(f"  Strong signals   : {stats['strong']}")
    unclassified = stats["total"] - stats["classified"]
    if unclassified:
        print(f"  Pending classify : {unclassified}  (run: python -m src.main classify)")

    try:
        demand = get_job_trends_summary()
        if demand:
            print("\nJob demand (this week, top skills):")
            for skill, count in list(demand.items())[:8]:
                print(f"  {skill:<30} {count} postings")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="career-intel",
        description=(
            "Career Intelligence Assistant — "
            "monitor industry signals for career decision support."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # collect
    sub.add_parser(
        "collect", help="Fetch articles from all configured RSS feeds"
    ).set_defaults(func=cmd_collect)

    # collect-press
    sub.add_parser(
        "collect-press",
        help="Fetch company newsrooms and targeted Google News monitors",
    ).set_defaults(func=cmd_collect_press)

    # collect-jobs
    sub.add_parser(
        "collect-jobs",
        help="Fetch job market signals (Bundesagentur + Indeed RSS)",
    ).set_defaults(func=cmd_collect_jobs)

    # classify
    p_classify = sub.add_parser("classify", help="Classify all unclassified articles")
    p_classify.add_argument(
        "--llm",
        choices=["openai", "claude"],
        default=None,
        metavar="PROVIDER",
        help="Use LLM classifier: 'claude' (requires ANTHROPIC_API_KEY, recommended) "
             "or 'openai' (requires OPENAI_API_KEY)",
    )
    p_classify.set_defaults(func=cmd_classify)

    # report
    p_report = sub.add_parser("report", help="Generate weekly Markdown + HTML report")
    p_report.add_argument(
        "--week",
        default="current",
        metavar="WEEK",
        help="Week to report: 'current' (default), 'last', or 'YYYY-WW'",
    )
    p_report.add_argument(
        "--format",
        choices=["md", "html", "both"],
        default="both",
        dest="format",
        help="Output format: md, html, or both (default: both)",
    )
    p_report.set_defaults(func=cmd_report)

    # skill-gap
    sub.add_parser(
        "skill-gap",
        help="Print skill gap analysis comparing CV claims vs job market demand",
    ).set_defaults(func=cmd_skill_gap)

    # send-email
    p_email = sub.add_parser(
        "send-email", help="Send the weekly HTML report as an email digest"
    )
    p_email.add_argument(
        "--week",
        default="current",
        metavar="WEEK",
        help="Which report to send: 'current', 'last', or 'YYYY-WW'",
    )
    p_email.set_defaults(func=cmd_send_email)

    # run-weekly
    p_weekly = sub.add_parser(
        "run-weekly",
        help="Full pipeline: collect + collect-press + collect-jobs + classify + report + email",
    )
    p_weekly.add_argument(
        "--llm",
        choices=["openai", "claude"],
        default=None,
        metavar="PROVIDER",
        help="Use LLM classifier during classify step",
    )
    p_weekly.add_argument(
        "--week", default="current", metavar="WEEK"
    )
    p_weekly.add_argument(
        "--format", choices=["md", "html", "both"], default="both", dest="format"
    )
    p_weekly.set_defaults(func=cmd_run_weekly)

    # status
    sub.add_parser("status", help="Show database and job market statistics").set_defaults(
        func=cmd_status
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
