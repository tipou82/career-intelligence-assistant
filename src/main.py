"""CLI entry point.

Usage:
    python -m src.main collect
    python -m src.main classify
    python -m src.main report [--week current|last|YYYY-WW]
    python -m src.main run-weekly
    python -m src.main status
"""

import argparse
import sys


def cmd_collect(args: argparse.Namespace) -> None:
    from .collect_rss import collect_all

    print("Collecting RSS feeds...")
    stats = collect_all()
    print(
        f"  Done.  Fetched: {stats['fetched']}  |  "
        f"New: {stats['new']}  |  Duplicates skipped: {stats['skipped']}"
    )


def cmd_classify(args: argparse.Namespace) -> None:
    from .classify_articles import classify_all

    print("Classifying articles...")
    stats = classify_all()
    print(f"  Done.  Classified: {stats['classified']}")


def cmd_report(args: argparse.Namespace) -> None:
    from .generate_weekly_report import generate_report

    week = getattr(args, "week", "current")
    print(f"Generating report for week: {week} ...")
    filepath = generate_report(week)
    print(f"  Saved: {filepath}")


def cmd_run_weekly(args: argparse.Namespace) -> None:
    print("=" * 55)
    print("  Career Intelligence Assistant – Weekly Pipeline")
    print("=" * 55)
    cmd_collect(args)
    cmd_classify(args)
    cmd_report(args)
    print("=" * 55)
    print("  Weekly run complete.")
    print("=" * 55)


def cmd_status(args: argparse.Namespace) -> None:
    from .database import get_stats, init_db

    init_db()
    stats = get_stats()
    print("Database status:")
    print(f"  Total articles   : {stats['total']}")
    print(f"  Classified       : {stats['classified']}")
    print(f"  Strong signals   : {stats['strong']}")
    unclassified = stats["total"] - stats["classified"]
    if unclassified:
        print(f"  Pending classify : {unclassified}  (run: python -m src.main classify)")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="career-intel",
        description=(
            "Career Intelligence Assistant — "
            "monitor industry signals for career decision support."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("collect", help="Fetch articles from all configured RSS feeds").set_defaults(
        func=cmd_collect
    )

    sub.add_parser("classify", help="Classify all unclassified articles").set_defaults(
        func=cmd_classify
    )

    p_report = sub.add_parser("report", help="Generate weekly Markdown report")
    p_report.add_argument(
        "--week",
        default="current",
        metavar="WEEK",
        help="Week to report: 'current' (default), 'last', or 'YYYY-WW'",
    )
    p_report.set_defaults(func=cmd_report)

    sub.add_parser(
        "run-weekly",
        help="Full pipeline: collect → classify → report",
    ).set_defaults(func=cmd_run_weekly)

    sub.add_parser("status", help="Show database statistics").set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
