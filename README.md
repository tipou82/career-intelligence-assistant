# Career Intelligence Assistant — Xi

A lightweight Python CLI tool that monitors the German cultural-sector job market,
extracts career-relevant signals, and generates a weekly decision-support brief for
a cultural project manager re-entering the German labour market.

**Current mode:** `external_transition`

**Target positioning:**
*Projektmanager*in Kultur for education programs, event production, music institutions
and exhibitions in the Stuttgart / Leonberg / Ludwigsburg / Böblingen region.*

**Primary goals:**
- Re-enter the German cultural-sector labour market with a credible mid-level
  project-management profile
- Prioritise education programs (Musikvermittlung) and event production as primary;
  classical-music institutions and museums as secondary
- Local first — Leonberg, Stuttgart, Böblingen, Ludwigsburg — remote BW/DE as fallback
- Close the German oral-fluency gap to confident interview level
- Convert Google Project Manager (Coursera) + Professional Scrum Master I into
  finished, visible credentials

This is **not** a news aggregator. It is a structured **career decision-support tool**
that maps cultural-sector signals to a personal skill matrix and produces a weekly
Markdown + HTML report with:

- **Career Actions This Week** — target role clusters, organisations to contact,
  networking targets, 7-day action plan
- **External Market Fit** — how Xi's profile maps to education programs, event
  production, music institutions, museums/exhibitions and PR/communication
- **Actionability scoring** — every signal rated for how much it should change
  job-search actions this week
- Skill priority table, learning allocation (capped at 15 h/week), risks to ignore

---

## Quick Start

### 1. Install

```bash
cd career-intelligence-assistant-xi
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set your Anthropic API key (for accurate LLM classification)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

> Without the key the tool still works using rule-based classification — less accurate but free.

### 3. Run the weekly pipeline

```bash
python -m src.main run-weekly --llm claude
```

This runs four steps:

1. **Collect** — fetches articles from ~25 cultural-sector RSS feeds
   (nmz, Backstage PRO, nachtkritik, FAZ Feuilleton, SZ Kultur, SWR Kultur,
   Stuttgarter Zeitung, Bachtrack, Slipped Disc, …)
2. **Collect press** — fetches Google News monitors for target organisations
   (Stuttgarter Liederhalle, HMDK Stuttgart, Schlossfestspiele Ludwigsburg, …)
3. **Classify** — sends each article to Claude Haiku for topic/skill/region tagging
   (~€0.10–0.30 per full run)
4. **Report** — generates `reports/weekly_career_brief_YYYY-WW.md` and `.html`

### 4. Open the report

```
reports/weekly_career_brief_2026-20.html   ← open in browser
reports/weekly_career_brief_2026-20.md     ← open in any Markdown viewer
```

---

## Weekly Workflow

After the first setup, the routine is:

```bash
source .venv/bin/activate
python -m src.main run-weekly --llm claude
```

Run once a week (e.g. Monday morning before job applications). Each run only
downloads and classifies articles it has not seen before, so it stays fast and
cheap after the first run.

---

## All Commands

```bash
# ── Core pipeline ──────────────────────────────────────────────
python -m src.main full-run-weekly --llm claude   # recommended: pipeline + push + email
python -m src.main run-weekly --llm claude        # pipeline only (no push/email)

# ── Individual steps ───────────────────────────────────────────
python -m src.main collect                     # fetch RSS articles
python -m src.main collect-press               # fetch organisation newsrooms + Google News
python -m src.main collect-jobs                # fetch job market signals (Bundesagentur + Indeed)
python -m src.main classify                    # rule-based classification (free)
python -m src.main classify --llm claude       # Claude Haiku classification (~€0.001/10 articles)

# ── Reports ────────────────────────────────────────────────────
python -m src.main report                      # current week, Markdown + HTML
python -m src.main report --week last          # previous week
python -m src.main report --week 2026-20       # specific week
python -m src.main report --format html        # HTML only
python -m src.main report --format md          # Markdown only

# ── Email digest ───────────────────────────────────────────────
python -m src.main send-email                  # send HTML report via Gmail SMTP
python -m src.main send-email --week last      # send last week's report

# ── Analysis ───────────────────────────────────────────────────
python -m src.main qualifications              # qualification recommendations
python -m src.main skill-gap                   # CV self-ratings vs job market demand
python -m src.main status                      # database stats + job demand summary
```

---

## Qualification Layer

The qualification layer recommends targeted actions from `config/qualification_actions.yaml`.
It follows this rule:

> **Target role → required proof → current gap → smallest credible step → visible output → CV/interview integration**

Current must-have actions:
1. Weekly application pipeline (3 applications + 1 outreach/week)
2. Spoken German practice (tandem + coaching, 3 h/week)
3. Complete Google PM + Scrum Master I certifications
4. Bilingual CV + LinkedIn positioning as Projektmanager*in Kultur
5. Three Musikvermittlung concept sketches for education-program interviews

---

## What the Report Contains

In `external_transition` mode, each weekly report has these sections:

| Section | Content |
|---|---|
| 1. Executive Summary | Strong/weak signal count, key sectors and organisations |
| **2. Career Actions This Week** | Role clusters, top organisations, networking, 7-day plan |
| 3. Strong Signals | Top articles with full analysis + actionability score |
| 4. Weak Signals / Watchlist | Top 15 by actionability (linked) |
| 5. Skill Priority Update | 7-column table: skill · priority · urgency · depth · change · reason · effort |
| 6. Learning Allocation | Grouped plan (capped at 15 h/week) |
| 7. Career Positioning Advice | How this week's signals affect positioning |
| 8. Risks and Hype to Ignore | What to filter out |
| **External Market Fit** | Profile mapping to education / event production / music / museum / PR |
| Source List | Signal links |

---

## Skill Matrix

The skill matrix (`config/skill_matrix.yaml`) is configured for **cultural-PM external transition**:

```
Deep Focus (job search first):
  External job search and applications · German oral fluency + interview communication
  Google PM + Scrum Master I completion · CV / LinkedIn / portfolio

Serious (build steadily):
  Cultural project management practice (DE conventions) · Music education / Musikvermittlung
  Event production and coordination · PR and media knowledge maintenance

Lightweight (awareness only):
  AI tools for cultural administration · Exhibitions and museum education
  Local networking (Stuttgart region) · Cultural policy and funding awareness
```

Weekly hours cap is **15 h** (5 h job search + 10 h learning).

---

## Configuration Reference

### Updating CV self-ratings — `config/cv_skills.yaml`

Edit after each milestone (finished certification, interview completed, contract signed).
Fields:

```yaml
- name: "Music education and Musikvermittlung"   # must match skill_matrix.yaml exactly
  self_rating: 4                                 # 0–10: 0=not started, 4=awareness, 7=proficient
  cv_claimed: false
  evidence: >
    ...what project or experience backs this rating
  limitations: >
    ...what could be challenged in an interview
```

---

## Email Setup (Gmail → any address)

**Step 1** — Create a Gmail App Password at
[myaccount.google.com → Security → App passwords](https://myaccount.google.com/apppasswords).

**Step 2** — Store the password as an environment variable:

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

> `config/email.yaml` is gitignored — never commit credentials.

---

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

105 tests covering scoring logic, signal filtering, skill table generation,
learning allocation, actionability scoring, career mode loading, trigger
detection, source reliability tiers, and weak signal sorting.

---

## Architecture

```
config/
  sources.yaml              # ~25 cultural-sector RSS feeds
  pressreleases.yaml        # organisation newsrooms + Google News monitors
  jobs.yaml                 # job queries (Bundesagentur + Indeed)
  skill_matrix.yaml         # cultural-PM skill priorities, triggers, learning tasks
  keywords.yaml             # cultural-sector vocabulary for classification
  companies.yaml            # tracked organisations (Stuttgart region + DACH)
  cv_skills.yaml            # self-rated skills (for gap analysis)
  qualification_actions.yaml # qualification and gap-closure action plan
  email.yaml                # SMTP config (gitignored)

src/
  collect_rss.py            # RSS collector
  collect_pressreleases.py  # organisation newsroom + Google News collector
  collect_jobs.py           # job market signal collector (Bundesagentur + Indeed)
  classify_articles.py      # rule-based classifier + LLMClassifier interface
  llm_classifier.py         # AnthropicClassifier (Haiku) tuned for cultural PM
  score_relevance.py        # cultural-PM relevance + actionability scorer
  generate_weekly_report.py # Markdown + HTML report generator
  skill_gap.py              # CV vs job demand gap analysis
  email_digest.py           # SMTP email sender
  database.py               # SQLite schema and queries
  main.py                   # CLI entry point

data/articles.sqlite        # local article store (auto-created, gitignored)
reports/                    # generated weekly reports
```

---

## Limitations

- Rule-based classification (without `--llm`) relies on keyword matching and will
  miss paraphrased cultural-sector signals.
- LLM classification (Claude Haiku) is more accurate but not perfect.
- Weak signals are capped at 15 per report; some relevant signals may be suppressed.
- The `career_actionability_score` is rule-based; it cannot account for seniority
  requirements, salary range, or family constraints.
- `config/email.yaml` is gitignored. Never commit it.

---

_Built as a personal career decision-support tool. Not affiliated with any
organisation listed._
