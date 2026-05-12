# Career Intelligence Assistant

A lightweight Python CLI tool that monitors industry news, extracts career-relevant signals, and generates a weekly decision-support brief.

**Target positioning:** *AI-augmented safety systems engineer for embedded AI / robotics / ADAS systems*

This is **not** a news aggregator. It is a structured **career decision-support tool** that maps industry signals to a personal T-shaped skill matrix and produces a weekly Markdown + HTML report with actionable recommendations.

---

## Quick Start

### 1. Install

```bash
cd career_intelligence_assistant
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set your Anthropic API key (for accurate LLM classification)

```bash
# Add to your shell profile (~/.bashrc or ~/.zshrc) for persistence
export ANTHROPIC_API_KEY=sk-ant-...
```

> Without the key the tool still works using rule-based classification — less accurate but free.

### 3. Run the weekly pipeline

```bash
python -m src.main run-weekly --llm claude
```

This runs four steps automatically:

1. **Collect** — fetches articles from ~25 RSS feeds (IEEE, SAE, Nikkei, Handelsblatt, Robot Report, …)
2. **Collect press** — fetches company newsrooms + targeted Google News monitors (Bosch, NEURA, NVIDIA, …)
3. **Classify** — sends each article to Claude Haiku for topic/skill/region tagging (~$0.15–0.40 per full run)
4. **Report** — generates `reports/weekly_career_brief_YYYY-WW.md` and `.html`

### 4. Open the report

```
reports/weekly_career_brief_2026-20.html   ← open in browser
reports/weekly_career_brief_2026-20.md     ← open in any Markdown viewer
```

---

## Weekly Workflow

After the first setup, your routine is:

```bash
source .venv/bin/activate
python -m src.main run-weekly --llm claude
```

Run it once a week (e.g. Monday morning). Each run only downloads and classifies articles it has not seen before, so it stays fast and cheap after the first run.

### Analyse only the last 5 days

The report covers the current ISO week. To also cover the previous week:

```bash
python -m src.main report --week current --format both
python -m src.main report --week last    --format both
```

### Reclassify recent articles with Claude (after switching from rule-based)

```bash
# Reset classification for the last 5 days and reclassify with Claude
python3 -c "
import sqlite3; from datetime import date, timedelta
conn = sqlite3.connect('data/articles.sqlite')
conn.execute('''UPDATE articles SET classification=NULL, relevance_score=0.0,
    confidence_level='low', signal_strength='noise', recommended_action='watch',
    classified_at=NULL WHERE date(published_date) BETWEEN ? AND ?''',
    ((date.today()-timedelta(days=4)).isoformat(), date.today().isoformat()))
conn.commit(); conn.close(); print('Done')
"
python -m src.main classify --llm claude
```

---

## All Commands

```bash
# ── Core pipeline ──────────────────────────────────────────────
python -m src.main run-weekly                  # full pipeline (rule-based)
python -m src.main run-weekly --llm claude     # full pipeline (Claude Haiku)

# ── Individual steps ───────────────────────────────────────────
python -m src.main collect                     # fetch RSS articles
python -m src.main collect-press               # fetch company newsrooms + Google News
python -m src.main collect-jobs                # fetch job market signals (Bundesagentur + Indeed)
python -m src.main classify                    # rule-based classification (free)
python -m src.main classify --llm claude       # Claude Haiku classification (~$0.001/10 articles)
python -m src.main classify --llm openai       # OpenAI GPT-4o-mini (alternative)

# ── Reports ────────────────────────────────────────────────────
python -m src.main report                      # current week, Markdown + HTML
python -m src.main report --week last          # previous week
python -m src.main report --week 2026-19       # specific week
python -m src.main report --format html        # HTML only
python -m src.main report --format md          # Markdown only

# ── Email digest ───────────────────────────────────────────────
python -m src.main send-email                  # send HTML report via Gmail SMTP
python -m src.main send-email --week last      # send last week's report

# ── Analysis ───────────────────────────────────────────────────
python -m src.main skill-gap                   # CV self-ratings vs job market demand
python -m src.main status                      # database stats + job demand summary
```

---

## Email Setup (Gmail → any address)

**Step 1** — Create a Gmail App Password at [myaccount.google.com → Security → App passwords](https://myaccount.google.com/apppasswords) (requires 2-step verification).

**Step 2** — Store the password as an environment variable (**never in the config file**):

```bash
echo 'export EMAIL_PASSWORD="your-app-password"' >> ~/.bashrc
source ~/.bashrc
```

**Step 3** — Edit `config/email.yaml`:

```yaml
enabled: true
smtp_host: "smtp.gmail.com"
smtp_port: 465
use_ssl: true
username: "your.address@gmail.com"
password: ""       # leave blank — read from EMAIL_PASSWORD env var
from: "your.address@gmail.com"
to: "recipient@example.com"
```

**Step 4** — Test:

```bash
python -m src.main send-email --week current
```

> `config/email.yaml` is in `.gitignore` and will never be committed to the repository.

---

## What the Report Contains

Each weekly report has 8 sections:

| Section | Content |
|---|---|
| 1. Executive Summary | Count of strong/weak signals, key industries and companies |
| 2. Strong Signals | Top articles with full analysis: development, region, technologies, career relevance, recommended action |
| 3. Weak Signals / Watchlist | Articles that may become important — monitor but don't act yet |
| 4. Skill Priority Update | 7-column table: skill · priority · urgency · required depth · change · reason · weekly effort |
| 5. Learning Allocation | Grouped learning plan by strategic focus (Deep Focus / Serious / Lightweight) |
| 6. Career Positioning Advice | How this week's signals affect your positioning |
| 7. Risks and Hype to Ignore | What to filter out |
| 8. Source List | All articles used, with links |

---

## Skill Matrix

The skill matrix (`config/skill_matrix.yaml`) is **T-shaped**:

```
Deep core (do intensively):
  C++20 safety logic · ROS2 · AI perception monitoring · Soft skills · Portfolio

Broad supporting layer (build steadily):
  Python · Linux · ISO 13849/CMSE · SOTIF/ISO PAS 8800 · Requirements traceability

Lightweight (maintain awareness):
  MBSE/SysML2 · QNX concepts · MCP workflows · Career assistant
```

Each skill has three dimensions:

| Dimension | Range | Meaning |
|---|---|---|
| `priority` | 1–5 | Long-term career leverage |
| `urgency` | 1–5 | Importance in the next 3 months |
| `required_depth` | 1–5 | How deep the knowledge must go |

Triggers in the skill matrix automatically show ↑ in the weekly table when relevant signals appear. For example: an article about "ISO 13849 collaborative robot safety function" triggers ↑ on the ISO 13849/CMSE skill row.

---

## Relevance Scoring

Each article is scored 1–10:

| Factor | Weight | Description |
|---|---|---|
| Skill relevance | 30% | Match against target skills (ROS2, ISO 26262, SOTIF, fault injection, …) |
| Career impact | 25% | High-value domain + skill combinations (e.g. robotics + ROS2) |
| Domain relevance | 22% | Match against target industries (robotics, automotive, ADAS, …) |
| Source reliability | 13% | IEEE/SAE 0.95+ · news agencies 0.87–0.92 · blogs 0.55–0.68 |
| Region relevance | 10% | Germany 1.0 · Japan/China 0.8 · USA 0.8 |

Articles scoring ≥ 6.5 → **strong signal**. Articles 3.5–6.4 → **weak signal**. Below → noise.

---

## Architecture

```
config/
  sources.yaml          # ~25 RSS feeds with reliability scores
  pressreleases.yaml    # company newsrooms + Google News monitors
  jobs.yaml             # job search queries (Bundesagentur + Indeed)
  skill_matrix.yaml     # T-shaped skill priorities, triggers, learning tasks
  keywords.yaml         # industry/region/technology/skill keywords
  companies.yaml        # tracked companies with tier and aliases
  cv_skills.yaml        # your self-rated skills (for gap analysis)
  email.yaml            # SMTP config (gitignored — no credentials in repo)

src/
  collect_rss.py            # RSS collector (15s timeout per feed)
  collect_pressreleases.py  # company newsroom + Google News collector
  collect_jobs.py           # job market signal collector
  classify_articles.py      # rule-based classifier + LLMClassifier interface
  llm_classifier.py         # AnthropicClassifier (Haiku) + OpenAIClassifier
  score_relevance.py        # weighted multi-factor relevance scorer
  generate_weekly_report.py # Markdown + HTML report generator
  skill_gap.py              # CV vs job demand gap analysis
  email_digest.py           # SMTP email sender
  database.py               # SQLite schema and queries
  main.py                   # CLI entry point

data/articles.sqlite        # local article store (auto-created, gitignored)
reports/                    # generated Markdown + HTML reports
```

---

## Configuration Reference

### Adding an RSS Feed — `config/sources.yaml`

```yaml
feeds:
  - name: "My Source"
    url: "https://example.com/feed.rss"
    category: "technical"      # technical | automotive | robotics | embedded | news
    reliability: 0.85          # 0.0–1.0; used when source not in tier table
    regions: ["germany"]
    industries: ["automotive"]
```

### Updating your CV self-ratings — `config/cv_skills.yaml`

Update `self_rating` (0–10) and `cv_claimed` after each learning sprint. The `skill-gap` command compares these against job market demand signals.

---

## Running Tests

```bash
pytest tests/ -v
```

82 tests covering scoring logic, signal filtering, skill table generation, learning allocation, trigger detection and source reliability tiers.

---

## Limitations

- This tool is for personal career intelligence, **not financial advice**.
- It does not guarantee job-market predictions.
- Rule-based classification (`classify` without `--llm`) relies on keyword matching and will miss nuanced signals.
- LLM classification improves accuracy but the model can still misclassify ambiguous articles.
- **Human review is required before changing career direction.**
- RSS feeds may change URLs or stop publishing without notice.

---

_Built as a personal career decision-support tool. Not affiliated with any company or organization listed._
