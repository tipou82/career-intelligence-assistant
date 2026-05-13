# Career Intelligence Assistant

A lightweight Python CLI tool that monitors industry news, extracts career-relevant signals, and generates a weekly decision-support brief for a senior safety architect in external transition.

**Current mode:** `external_transition`

**Target positioning:**
*Senior System Safety / Functional Safety Architect for safety-critical embedded systems, robotics, ADAS, industrial automation, and AI-enabled systems.*

**Primary goals:**
- Protect family income and employability through a realistic external transition
- Identify senior safety architecture roles in Germany / Europe
- Prioritize ISO 26262, ISO 13849/CMSE, SOTIF, IEC 61508/62061, embedded AI safety as differentiators
- Consulting / TÜV / assessment track as parallel option

This is **not** a news aggregator. It is a structured **career decision-support tool** that maps industry signals to a personal skill matrix and produces a weekly Markdown + HTML report with:

- **Career Actions This Week** — concrete job search steps, companies to contact, keywords
- **External Market Fit** — where your profile maps to the market
- **Actionability scoring** — every signal rated for how much it should change your actions this week
- Skill priority table, learning allocation (hard-capped at 15–20 h/week), risks to ignore

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
python -m src.main full-run-weekly --llm claude   # recommended: pipeline + push + email
python -m src.main run-weekly --llm claude        # pipeline only (no push/email)

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

## Career Mode

Set `career_mode` in `config/skill_matrix.yaml`:

| Mode | Description |
|---|---|
| `external_transition` | Optimised for senior safety architect job search in Germany/Europe. Adds "Career Actions This Week" and "External Market Fit" sections. Boosts Germany/Europe signals. Weights actionability at 20%. |
| `default` | General industry monitoring. No career-specific sections. |

**To switch modes**, edit one line:
```yaml
# config/skill_matrix.yaml
career_mode: external_transition   # or: default
```

### external_transition mode features

- **Section 2: Career Actions This Week** — top role clusters, companies to contact, CV keywords, networking targets, 7-day action plan
- **External Market Fit** — maps your profile to: automotive safety, robotics/machine safety, industrial automation, consulting/TÜV, adjacent sectors
- **Actionability score** (0–10) on every article — measures whether this signal should change your actions this week (hiring signal = 9+, generic GenAI = 1–2)
- **Weak signals capped at 15** by actionability score, with theme summary for the rest
- **Weekly learning allocation hard-capped** at `weekly_hours_cap` (default 18h) — job search and interview prep always appear first
- **Scoring weights** shifted toward Germany/Europe regional fit (15%) and actionability (20%)

---

## What the Report Contains

In `external_transition` mode, each weekly report has these sections:

| Section | Content |
|---|---|
| 1. Executive Summary | Count of strong/weak signals, key industries and companies |
| **2. Career Actions This Week** | Role clusters, companies, CV keywords, networking, 7-day plan |
| 3. Strong Signals | Top articles with full analysis + actionability score |
| 4. Weak Signals / Watchlist | Top 15 by actionability (linked, with language flag) |
| 5. Skill Priority Update | 7-column table: skill · priority · urgency · depth · change · reason · effort |
| 6. Learning Allocation | Grouped plan (hard-capped at weekly_hours_cap h) |
| 7. Career Positioning Advice | How this week's signals affect positioning |
| 8. Risks and Hype to Ignore | What to filter out |
| **External Market Fit** | Profile mapping to automotive / robotics / industrial / consulting |
| Source List | Strong + shown weak signals, with links |

---

## Skill Matrix

The skill matrix (`config/skill_matrix.yaml`) is configured for **external transition**:

```
Deep Focus (job search first):
  External job search · Interview communication · Functional safety architecture
  ISO 13849/CMSE · GitHub portfolio

Serious (technical credibility):
  ROS2 · C++20 · AI perception monitoring · SOTIF/ISO PAS 8800 · Linux

Lightweight (awareness only):
  MCP workflows · Career assistant · MBSE/SysML2 · General AI monitoring
```

Each skill has three dimensions plus a group:

| Field | Range | Meaning |
|---|---|---|
| `priority` | 1–5 | Long-term career leverage |
| `urgency` | 1–5 | Importance in the next 3 months |
| `required_depth` | 1–5 | How deep the knowledge must go |
| `weekly_hours_baseline` | 0–5 | Default weekly time allocation |

The `weekly_hours_cap` field hard-limits the total recommended learning hours per week. Deep Focus items are allocated first. If the cap is reached, later items are trimmed automatically.

Triggers in the skill matrix automatically show ↑ in the weekly table when relevant signals appear. For example: an article mentioning "ISO 13849" or "machinery safety" triggers ↑ on the ISO 13849/CMSE row.

---

## Relevance Scoring

Each article gets two scores:

**`relevance_score` (1–10):** How relevant is this signal to your profile?

| Factor | Default | `external_transition` | Description |
|---|---|---|---|
| Skill relevance | 30% | 25% | Match against target skills |
| Career impact | 25% | 15% | High-value domain+skill combos |
| Domain relevance | 22% | 15% | Target industries |
| Actionability | — | **20%** | Hiring signals, job openings, restructuring |
| Region (DE/EU) | 10% | **15%** | Germany 1.0 · Japan/China 0.8 |
| Source reliability | 13% | 10% | IEEE/SAE 0.95+ · blogs 0.55–0.68 |

**`career_actionability_score` (0–10):** Should this signal change your actions this week?

| Score | Meaning | Examples |
|---|---|---|
| 8–10 | Act now | Safety job openings, hiring signals, layoffs in target sector |
| 5–7 | Monitor | Company safety news, standards updates, technology signals |
| 1–4 | Ignore | Generic GenAI, consumer hype, demos without hiring/safety signal |

Articles scoring ≥ 6.5 → **strong signal**. Articles 3.5–6.4 → **weak signal** (shown top 15 by actionability). Below → noise.

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

Edit after each learning sprint or milestone. Fields:

```yaml
- name: "ISO 13849 and CMSE"    # must match skill_matrix.yaml exactly
  self_rating: 3                # 0–10: 0=not started, 3=awareness, 6=working, 8=proficient
  cv_claimed: false             # true = currently on CV
  evidence: >                   # what project or experience backs this rating
    Structured CMSE study ongoing; ISO 26262 transferable background.
  limitations: >                # what could be challenged in an interview
    No practical machinery project yet. CMSE certification pending.
```

The `skill-gap` command (`python -m src.main skill-gap`) compares your self-ratings against job market demand signals from `collect-jobs`.

**Important:** Ratings should be honest — conservative enough that you could defend every claim in a senior-level interview. The limitations field is the safety check: if you cannot fill it in honestly, the rating is probably too high.

---

## Running Tests

```bash
pytest tests/ -v
```

102 tests covering: scoring logic, signal filtering, skill table generation, learning allocation with hours cap, actionability scoring, career mode loading, trigger detection, source reliability tiers, and weak signal sorting.

---

## Limitations

### Classification accuracy
- Rule-based classification (`classify` without `--llm`) relies on keyword matching. It will miss signals in paraphrased text and may incorrectly tag off-topic articles that happen to contain tracked company names.
- LLM classification (Claude Haiku via `--llm claude`) is more accurate but not perfect. Ambiguous or multilingual articles may still be misclassified.
- Chinese (ZH) and Japanese (JA) articles are classified using substring matching — more reliable than English word-boundary matching but can still produce false positives on short titles.

### Signal coverage
- The tool covers ~25 RSS feeds plus targeted Google News monitors. It does not scrape LinkedIn job postings directly or monitor company career pages. Job market signals from `collect-jobs` are indicative counts, not exhaustive.
- Weak signals are capped at 15 per report (sorted by `career_actionability_score`). Articles below the threshold are summarised by theme only — some relevant signals may be suppressed.
- The `career_actionability_score` is rule-based (keyword heuristic). It cannot reason about context: a press release about "hiring safety engineers" will score high even if the role is in a country or sector not relevant to you.

### Scoring and weights
- The `external_transition` scoring weights (20% actionability, 15% Germany/Europe region) are a heuristic calibration, not a validated career model. They prioritise Germany/Europe signals but cannot account for individual employer preferences or market conditions at the time of your search.
- The tool does not know your specific salary requirements, notice period, family constraints, or target company shortlist. Use the report as input to your judgment, not as a decision-maker.
- Bosch Japan is intentionally kept as an optional signal — the tool does not treat it as the default or primary career path.

### Skill gap analysis
- `cv_skills.yaml` self-ratings are only as reliable as your honesty. The gap analysis compares ratings against job demand keyword counts — it cannot assess interview performance, cultural fit, or management-level expectations.
- QNX, ISO 13849/CMSE, and SOTIF/ISO PAS 8800 are rated conservatively because they have limited or no practical project backing. Do not let the tool prompt you to overclaim these on a CV.

### General
- This tool is for personal career intelligence, **not financial advice or career guarantees**.
- It does not predict which company will hire you or how long your job search will take.
- **Human review is required before acting on any report recommendation.** The tool supports your decision-making — it does not make decisions for you.
- RSS feeds may change URLs or go offline. Run `collect` + `collect-press` weekly to stay current; stale data degrades report quality.
- `config/email.yaml` contains SMTP credentials and is gitignored. Never commit it.

---

_Built as a personal career decision-support tool. Not affiliated with Bosch or any other company listed._
