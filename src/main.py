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
    print("Collecting RSS feeds...")
    stats = _run_collect(args)
    print(f"  Done.  Fetched: {stats['fetched']}  New: {stats['new']}  Skipped: {stats['skipped']}")


def cmd_collect_press(args: argparse.Namespace) -> None:
    print("Collecting company press releases and newsroom feeds...")
    stats = _run_collect_press(args)
    print(f"  Done.  Fetched: {stats['fetched']}  New: {stats['new']}  Skipped: {stats['skipped']}")


def cmd_collect_jobs(args: argparse.Namespace) -> None:
    print("Collecting job market signals...")
    stats = _run_collect_jobs(args)
    print(f"  Done.  Searched: {stats['searched']}  Saved: {stats['saved']}  Errors: {stats['errors']}")


def cmd_classify(args: argparse.Namespace) -> None:
    llm = getattr(args, "llm", None)
    label = {"claude": "Claude (claude-haiku-4-5)", "openai": "OpenAI"}.get(llm, "rule-based")
    print(f"Classifying articles ({label})...")
    stats = _run_classify(args)
    print(f"  Done.  Classified: {stats['classified']}")


def cmd_report(args: argparse.Namespace) -> None:
    week = getattr(args, "week", "current")
    fmt = getattr(args, "format", "both")
    print(f"Generating report (week={week}, format={fmt})...")
    _run_report(args)
    print("  Done.")


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
    import time

    llm = getattr(args, "llm", None)
    week = getattr(args, "week", "current")
    fmt = getattr(args, "format", "both")

    WIDTH = 60
    print("=" * WIDTH)
    print("  Career Intelligence Assistant – Weekly Pipeline")
    llm_label = f"  Classifier : {llm} (LLM)" if llm else "  Classifier : rule-based"
    print(llm_label)
    print("=" * WIDTH)

    steps = [
        ("1/5  Collect RSS feeds",           lambda: _run_collect(args)),
        ("2/5  Collect press & newsrooms",   lambda: _run_collect_press(args)),
        ("3/5  Collect job signals",         lambda: _run_collect_jobs(args)),
        ("4/5  Classify articles",           lambda: _run_classify(args)),
        ("5/5  Generate report",             lambda: _run_report(args)),
    ]

    results = {}
    pipeline_start = time.time()

    for label, fn in steps:
        print(f"\n── {label} {'─' * (WIDTH - len(label) - 4)}")
        t0 = time.time()
        try:
            result = fn()
            elapsed = time.time() - t0
            results[label] = ("ok", result, elapsed)
            print(f"     ✓ done in {elapsed:.1f}s")
        except Exception as exc:
            elapsed = time.time() - t0
            results[label] = ("error", str(exc), elapsed)
            print(f"     ✗ error: {exc}")

    # Auto-send email if configured
    from .email_digest import _load_config as _email_cfg
    cfg = _email_cfg()
    if cfg.get("enabled", False):
        print(f"\n── 6/6  Send email digest {'─' * (WIDTH - 24)}")
        try:
            cmd_send_email(args)
        except Exception as exc:
            print(f"     ✗ error: {exc}")

    total = time.time() - pipeline_start
    print("\n" + "=" * WIDTH)
    print("  Summary")
    print("=" * WIDTH)
    for label, (status, info, elapsed) in results.items():
        icon = "✓" if status == "ok" else "✗"
        # Show concise info per step
        if isinstance(info, dict):
            parts = [f"{k}={v}" for k, v in info.items() if isinstance(v, int)]
            detail = "  " + "  ".join(parts) if parts else ""
        else:
            detail = f"  {info}" if info and status == "error" else ""
        print(f"  {icon}  {label}{detail}")
    print(f"\n  Total time: {total:.0f}s")
    print("=" * WIDTH)


# ── Step runners that return stats dicts ──────────────────────────────────

def _run_collect(args: argparse.Namespace) -> dict:
    from .collect_rss import collect_all
    stats = collect_all()
    print(f"     fetched={stats['fetched']}  new={stats['new']}  skipped={stats['skipped']}")
    return stats


def _run_collect_press(args: argparse.Namespace) -> dict:
    from .collect_pressreleases import collect_pressreleases
    stats = collect_pressreleases()
    print(f"     fetched={stats['fetched']}  new={stats['new']}  skipped={stats['skipped']}")
    return stats


def _run_collect_jobs(args: argparse.Namespace) -> dict:
    from .collect_jobs import collect_jobs
    stats = collect_jobs()
    print(f"     searched={stats['searched']}  saved={stats['saved']}  errors={stats['errors']}")
    return stats


def _run_classify(args: argparse.Namespace) -> dict:
    llm = getattr(args, "llm", None)
    llm_classifier = None
    if llm == "claude":
        from .llm_classifier import AnthropicClassifier
        llm_classifier = AnthropicClassifier()
    elif llm == "openai":
        from .llm_classifier import OpenAIClassifier
        llm_classifier = OpenAIClassifier()
    from .classify_articles import classify_all
    stats = classify_all(llm_classifier=llm_classifier)
    print(f"     classified={stats['classified']}")
    return stats


def _run_report(args: argparse.Namespace) -> dict:
    from .generate_weekly_report import generate_report
    from .skill_gap import analyse_skill_gap, render_gap_html
    week = getattr(args, "week", "current")
    fmt = getattr(args, "format", "both")
    gap_html = render_gap_html(analyse_skill_gap())
    saved = generate_report(week_label=week, fmt=fmt, skill_gap_html=gap_html)
    for fmt_key, path in saved.items():
        print(f"     [{fmt_key.upper()}] {path.name}")
    return {"formats": len(saved)}


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


def cmd_full_run_weekly(args: argparse.Namespace) -> None:
    """run-weekly + git push reports + send email."""
    import subprocess
    from pathlib import Path
    from datetime import date

    # 1. Run the standard weekly pipeline
    cmd_run_weekly(args)

    reports_dir = Path(__file__).parent.parent / "reports"
    week = getattr(args, "week", "current")
    from .generate_weekly_report import get_week_label
    week_label = get_week_label(week)

    WIDTH = 60
    print(f"\n── Push reports to git {'─' * (WIDTH - 22)}")

    # 2. Git add + commit + push the report files
    md_file = reports_dir / f"weekly_career_brief_{week_label}.md"
    html_file = reports_dir / f"weekly_career_brief_{week_label}.html"

    files_to_add = [str(p) for p in [md_file, html_file] if p.exists()]
    if not files_to_add:
        print("     No report files found to push.")
    else:
        today = date.today().isoformat()
        commit_msg = f"Weekly report {week_label} — generated {today}"
        try:
            subprocess.run(["git", "add"] + files_to_add, check=True, capture_output=True)
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True,
            )
            if result.returncode == 0:
                print("     No changes to commit (reports unchanged).")
            else:
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    check=True, capture_output=True,
                )
                subprocess.run(["git", "push"], check=True, capture_output=True)
                print(f"     ✓ Pushed: {', '.join(p.name for p in [md_file, html_file] if p.exists())}")
        except subprocess.CalledProcessError as exc:
            print(f"     ✗ Git error: {exc.stderr.decode().strip() if exc.stderr else exc}")

    # 3. Send email
    print(f"\n── Send email digest {'─' * (WIDTH - 20)}")
    try:
        cmd_send_email(args)
    except SystemExit:
        pass  # send-email calls sys.exit(1) on failure; already printed the error


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

    # full-run-weekly
    p_full = sub.add_parser(
        "full-run-weekly",
        help="run-weekly + git push reports + send email",
    )
    p_full.add_argument("--llm", choices=["openai", "claude"], default=None, metavar="PROVIDER")
    p_full.add_argument("--week", default="current", metavar="WEEK")
    p_full.add_argument("--format", choices=["md", "html", "both"], default="both", dest="format")
    p_full.set_defaults(func=cmd_full_run_weekly)

    # status
    sub.add_parser("status", help="Show database and job market statistics").set_defaults(
        func=cmd_status
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
