# Career Intelligence Assistant

A lightweight Python CLI tool that monitors industry news, extracts career-relevant signals, and generates a weekly decision-support brief — configurable for any role, domain, or geography.

**Not** a news aggregator. A structured **career decision-support tool** that maps industry signals to your personal skill matrix and produces a weekly Markdown + HTML report with:

- **Career Actions This Week** — concrete job search steps, companies to contact, keywords
- **Market Fit analysis** — where your profile maps to the current market
- **Actionability scoring** — every signal rated for how much it should change your actions this week
- Skill priority table, learning allocation (configurable weekly hour cap), risks to ignore

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/tipou82/career-intelligence-assistant.git
cd career-intelligence-assistant
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set your Anthropic API key (for LLM classification)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

> Without the key the tool works using rule-based classification — less accurate but free.

### 3. Configure your profile

Edit the config files in `config/` to match your target role, skills, and geography:

- **`config/skill_matrix.yaml`** — your career mode, target positioning, skills and weekly learning goals
- **`config/cv_skills.yaml`** — honest self-assessment of your current skills
- **`config/sources.yaml`** — RSS feeds to monitor (pre-configured with ~25 industry sources)
- **`config/keywords.yaml`** — industry/technology/region keywords for classification
- **`config/companies.yaml`** — companies to track
- **`config/pressreleases.yaml`** — company newsrooms and targeted Google News monitors

### 4. Run the weekly pipeline

```bash
python -m src.main run-weekly --llm claude
```

This runs four steps automatically:

1. **Collect** — fetches articles from configured RSS feeds
2. **Collect press** — fetches company newsrooms and targeted Google News monitors
3. **Classify** — tags each article by topic, skill, region, and company (Claude Haiku ~$0.15–0.40 per run)
4. **Report** — generates `reports/weekly_career_brief_YYYY-WW.md` and `.html`

### 5. Open the report

```
reports/weekly_career_brief_YYYY-WW.html   ← open in browser
reports/weekly_career_brief_YYYY-WW.md     ← open in any Markdown viewer
```

---

## Weekly Workflow

After initial setup, your routine is:

```bash
source .venv/bin/activate
python -m src.main run-weekly --llm claude
```

Run once a week. Each run only downloads and classifies articles not yet seen, so it stays fast and cheap after the first run.

### Other useful commands

```bash
# Report for a specific week
python -m src.main report --week last --format both

# Classify only (without collecting new articles)
python -m src.main classify --llm claude

# Reclassify the last 5 days (e.g. after switching from rule-based to LLM)
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

# Check DB stats
python -m src.main status
```

---

## Career Modes

Set in `config/skill_matrix.yaml`:

```yaml
career_mode: external_transition   # or: default
```

### `external_transition` mode

Optimised for an active job search:

- **Section 2: Career Actions This Week** — top role clusters, companies to contact, CV keywords, networking targets, 7-day action plan
- **Market Fit** — maps your profile to target sectors
- **Actionability score** (0–10) on every article — measures whether this signal should change your actions this week
- **Weak signals capped at 15** by actionability score
- **Weekly learning allocation hard-capped** at `weekly_hours_cap` — job search and interview prep always appear first
- **Scoring weights** shifted toward regional fit and actionability (see Scoring section)

### `default` mode

General industry monitoring without job-search framing. Useful for staying current in your field while employed.

---

## What the Report Contains

In `external_transition` mode:

| Section | Content |
|---|---|
| 1. Executive Summary | Count of strong/weak signals, key industries and companies |
| **2. Career Actions This Week** | Role clusters, companies, CV keywords, networking, 7-day plan |
| 3. Strong Signals | Top articles with full analysis + actionability score |
| 4. Weak Signals / Watchlist | Top 15 by actionability (linked, with language flag) |
| 5. Skill Priority Update | 7-column table: skill · priority · urgency · depth · change · reason · effort |
| 6. Learning Allocation | Grouped plan (hard-capped at `weekly_hours_cap`) |
| 7. Career Positioning Advice | How this week's signals affect positioning |
| 8. Risks and Hype to Ignore | What to filter out |
| **Market Fit** | Profile mapping to target sectors |
| Source List | Strong + shown weak signals, with links |

---

## Configuring Your Profile

### `config/skill_matrix.yaml`

```yaml
career_mode: external_transition

strategic_target: >
  Describe your target role and positioning in 1–2 sentences.

primary_goals:
  - "Your first goal"
  - "Your second goal"

skills:
  - name: "Your Core Skill"
    group: deep_focus           # deep_focus | serious | lightweight
    priority: 5                 # 1–5: long-term career leverage
    urgency: 5                  # 1–5: importance in next 3 months
    required_depth: 4           # 1–5: how deep knowledge must go
    weekly_hours_baseline: 3    # default time allocation
    triggers: ["keyword1", "keyword2"]   # keywords that flag this skill in reports

weekly_hours_cap: 18            # hard limit on total recommended learning hours/week
```

### `config/cv_skills.yaml`

```yaml
skills:
  - name: "Your Core Skill"    # must match skill_matrix.yaml exactly
    self_rating: 7             # 0–10: 0=not started, 3=awareness, 6=working, 8=proficient
    cv_claimed: true           # true = currently on CV
    evidence: >
      Concrete projects or experience that backs this rating.
    limitations: >
      What is missing and could be challenged in an interview.
```

Ratings should be honest — conservative enough to defend in a senior interview. The `limitations` field is the safety check.

### `config/sources.yaml`

```yaml
feeds:
  - name: "My Source"
    url: "https://example.com/feed.rss"
    category: "technical"      # technical | automotive | robotics | embedded | news
    language: "en"             # en | de | zh | ja — controls flag in report
    reliability: 0.85          # 0.0–1.0; affects relevance scoring
    regions: ["germany"]
    industries: ["automotive"]
```

---

## Relevance Scoring

Each article gets two scores:

**`relevance_score` (1–10):** How relevant is this signal to your profile?

| Factor | `default` | `external_transition` | Description |
|---|---|---|---|
| Skill relevance | 30% | 25% | Match against target skills |
| Career impact | 25% | 15% | High-value domain+skill combos |
| Domain relevance | 22% | 15% | Target industries |
| Actionability | — | **20%** | Hiring signals, job openings, restructuring |
| Region fit | 10% | **15%** | Configurable per-region weights |
| Source reliability | 13% | 10% | IEEE/SAE 0.95+ · blogs 0.55–0.68 |

**`career_actionability_score` (0–10):** Should this signal change your actions this week?

| Score | Meaning | Examples |
|---|---|---|
| 8–10 | Act now | Job openings, hiring signals, layoffs in target sector |
| 5–7 | Monitor | Company news, standards updates, technology signals |
| 1–4 | Ignore | Generic hype, consumer demos, unrelated funding news |

Articles scoring ≥ 6.5 → **strong signal**. Articles 3.5–6.4 → **weak signal** (top 15 shown by actionability). Below → noise.

---

## Multi-language Support

The tool collects and classifies articles in English, German, Chinese, and Japanese. Each article is tagged with its source language and shown with a flag in the report (🇬🇧 EN · 🇩🇪 DE · 🇨🇳 ZH · 🇯🇵 JA).

Set `language:` on each feed in `sources.yaml`. The LLM classifier handles all four languages natively. The rule-based classifier uses keyword lists from `keywords.yaml`, which supports CJK substring matching.

---

## Architecture

```
config/
  sources.yaml          # RSS feeds with reliability scores and language tags
  pressreleases.yaml    # company newsrooms + Google News monitors
  jobs.yaml             # job search queries
  skill_matrix.yaml     # T-shaped skill priorities, triggers, learning tasks
  keywords.yaml         # industry/region/technology/skill keywords (multi-language)
  companies.yaml        # tracked companies with tier and aliases
  cv_skills.yaml        # self-rated skills (for gap analysis)
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

## Running Tests

```bash
pytest tests/ -v
```

Tests cover: scoring logic, signal filtering, skill table generation, learning allocation with hours cap, actionability scoring, career mode loading, trigger detection, source reliability tiers, and weak signal sorting.

---

## Limitations

### Classification accuracy
- Rule-based classification relies on keyword matching. It will miss signals in paraphrased text and may incorrectly tag off-topic articles that happen to contain tracked keywords.
- LLM classification (Claude Haiku) is more accurate but not perfect. Ambiguous or multilingual articles may still be misclassified.
- Chinese and Japanese articles use CJK substring matching — reliable for exact terms but can produce false positives on short titles.

### Signal coverage
- The tool covers the configured RSS feeds plus targeted Google News monitors. It does not scrape LinkedIn job postings directly or monitor company career pages.
- Weak signals are capped at 15 per report (sorted by actionability score). Some relevant signals may be suppressed.
- The `career_actionability_score` is rule-based. It cannot reason about context: a press release about "hiring safety engineers" will score high even if the role is in a country or sector not relevant to you.

### Scoring and weights
- The `external_transition` scoring weights are a heuristic calibration, not a validated career model. Use the report as input to your judgment, not as a decision-maker.
- The tool does not know your salary requirements, notice period, family constraints, or personal company shortlist.

### General
- This tool is for personal career intelligence, **not financial advice or career guarantees**.
- It does not predict which company will hire you or how long your job search will take.
- **Human review is required before acting on any report recommendation.**
- RSS feeds may change URLs or go offline. Run `collect` + `collect-press` weekly to stay current.
- `config/email.yaml` contains SMTP credentials and is gitignored. Never commit it.

---

_A personal career decision-support tool. Not affiliated with any company or organisation listed._
