"""Email digest — sends the weekly HTML report via SMTP.

Configuration: config/email.yaml
Environment variable overrides:
  EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD,
  EMAIL_FROM, EMAIL_TO

Usage:
    python -m src.main send-email --week current
    python -m src.main send-email --week 2026-20

Auto-send is triggered by run-weekly when email.yaml has enabled: true.
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config" / "email.yaml"


def _load_config() -> dict:
    """Load email config from YAML and apply environment variable overrides."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # Environment variable overrides
    overrides = {
        "smtp_host": os.environ.get("EMAIL_SMTP_HOST"),
        "smtp_port": os.environ.get("EMAIL_SMTP_PORT"),
        "username": os.environ.get("EMAIL_USERNAME"),
        "password": os.environ.get("EMAIL_PASSWORD"),
        "from": os.environ.get("EMAIL_FROM"),
        "to": os.environ.get("EMAIL_TO"),
    }
    for key, val in overrides.items():
        if val is not None:
            cfg[key] = int(val) if key == "smtp_port" else val

    return cfg


def send_report(
    html_path: Path,
    week_label: str,
    md_path: Optional[Path] = None,
) -> bool:
    """Send the weekly report as an HTML email.

    Args:
        html_path: Path to the HTML report file.
        week_label: ISO week label (e.g. '2026-20') used in the subject line.
        md_path: Optional Markdown file attached as plain-text alternative.

    Returns:
        True on success, False if disabled or on error.
    """
    cfg = _load_config()

    if not cfg.get("enabled", False):
        print("  [email] Digest disabled (set enabled: true in config/email.yaml).")
        return False

    required = ("smtp_host", "username", "password", "from", "to")
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        print(f"  [email] Missing config keys: {', '.join(missing)}")
        return False

    if not html_path.exists():
        print(f"  [email] HTML report not found: {html_path}")
        return False

    html_content = html_path.read_text(encoding="utf-8")
    subject_prefix = cfg.get("subject_prefix", "Career Brief")
    subject = f"{subject_prefix} – {week_label}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]

    # Plain-text fallback
    plain = (
        md_path.read_text(encoding="utf-8")
        if md_path and md_path.exists()
        else f"Career Intelligence Brief – {week_label}\n\nSee HTML version for full report."
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    smtp_host = cfg["smtp_host"]
    smtp_port = int(cfg.get("smtp_port", 465))
    use_ssl = cfg.get("use_ssl", True)

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                server.login(cfg["username"], cfg["password"])
                server.sendmail(cfg["from"], cfg["to"], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.login(cfg["username"], cfg["password"])
                server.sendmail(cfg["from"], cfg["to"], msg.as_string())
        print(f"  [email] Sent to {cfg['to']}: {subject}")
        return True
    except Exception as exc:
        print(f"  [email] Send failed: {exc}")
        return False
