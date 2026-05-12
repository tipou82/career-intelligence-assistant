# Career Intelligence Assistant

A lightweight Python CLI tool that monitors industry news, extracts career-relevant signals, and generates a weekly decision-support brief for a functional safety / embedded AI engineer targeting robotics, ADAS, and automotive roles.

This is **not** a news aggregator. It is a structured **career decision-support tool** that maps industry signals to a personal skill matrix and produces a weekly Markdown report with actionable recommendations.

---

## Why This Exists

Staying current in a fast-moving intersection of domains (functional safety, embedded AI, robotics, ADAS, software-defined vehicles) requires more than reading headlines. This tool:

- Monitors ~15 curated RSS sources across automotive, robotics, embedded, AI, and safety domains
- Classifies articles by industry, region, technology, and company
- Scores each article against a personal career profile (1–10 relevance score)
- Distinguishes strong signals from weak signals and noise
- Generates a weekly Markdown brief with skill priority updates and a learning plan
- Keeps a local SQLite database — no cloud dependency

---

## Architecture

```
career_intelligence_assistant/
├── config/
│   ├── sources.yaml        # RSS feeds with reliability scores
│   ├── companies.yaml      # Tracked companies with region + tier
│   ├── keywords.yaml       # Industry, region, technology, skill terms
│   └── skill_matrix.yaml   # Current skill priorities and weekly hour targets
├── data/
│   └── articles.sqlite     # Local article store (auto-created)
├── reports/
│   └── weekly_career_brief_YYYY-WW.md
└── src/
    ├── database.py             # SQLite schema, CRUD, query helpers
    ├── collect_rss.py          # feedparser-based RSS collector
    ├── classify_articles.py    # Rule-based classifier + LLM interface
    ├── score_relevance.py      # Weighted multi-factor relevance scorer
    ├── generate_weekly_report.py  # Markdown report generator
    └── main.py                 # CLI (argparse)
```

### Pipeline

```
collect_rss.py  →  database.py  →  classify_articles.py  →  score_relevance.py
                                                                      ↓
                                                    generate_weekly_report.py
                                                                      ↓
                                                    reports/weekly_career_brief_YYYY-WW.md
```

### Relevance Scoring

Each article receives a score from 1–10 using this weighted formula:

| Factor | Weight | Description |
|---|---|---|
| Skill relevance | 25% | Match against target skills (ROS2, ISO 26262, SOTIF, QNX, …) |
| Domain relevance | 20% | Match against target industries (robotics, automotive, ADAS, …) |
| Career impact | 20% | High-value domain+skill combinations (e.g. robotics+ROS2) |
| Company relevance | 15% | Tier-1 tracked companies score higher |
| Region relevance | 10% | Germany / Europe / Japan / USA prioritized |
| Source reliability | 10% | Academic / standards bodies score higher than blogs |

### Classification Tags

Each article is stored with:
- `industries`: detected industry domains
- `regions`: detected regions
- `companies`: matched tracked companies
- `technologies`: specific tech terms (ROS2, QNX, SOTIF, …)
- `skills`: career-relevant skill terms
- `relevance_score`: 1–10 weighted score
- `confidence_level`: high / medium / low (derived from source reliability)
- `signal_strength`: strong (≥7.0) / weak (4.0–6.9) / noise (<4.0)
- `recommended_action`: study_and_apply / monitor_closely / monitor / watch

### LLM Classifier Interface

`classify_articles.py` exposes an `LLMClassifier` Protocol. To use an LLM later:

```python
class MyLLMClassifier:
    def classify(self, title: str, summary: str) -> dict:
        # Call Anthropic / OpenAI API here
        # Return: industries, regions, companies, technologies,
        #         skills, confidence_level, recommended_action, source_reliability
        ...

from src.classify_articles import classify_all
classify_all(llm_classifier=MyLLMClassifier())
```

---

## Installation

```bash
cd career_intelligence_assistant
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

### Adding RSS Sources — `config/sources.yaml`

```yaml
feeds:
  - name: "My Source"
    url: "https://example.com/feed.rss"
    category: "technical"       # technical | automotive | robotics | embedded | news
    reliability: 0.8            # 0.0–1.0; affects confidence_level
    regions: ["germany"]
    industries: ["automotive"]
```

### Adjusting Skill Priorities — `config/skill_matrix.yaml`

```yaml
skills:
  - name: "ROS2"
    priority: "high"            # high | medium | low
    weekly_hours: 5             # target hours for the learning plan
    learning_task: "ROS2 safety nodes on Raspberry Pi"
    triggers:
      increase: ["ros2", "humanoid", "physical ai"]
      decrease: []
```

### Tracked Companies — `config/companies.yaml`

Companies are organized by sector with a `tier` (1 = highest career relevance) and a list of `aliases` for matching.

### Keywords — `config/keywords.yaml`

Edit `industries.domain_map` to add new domain markers, `technologies.terms` for tech keywords, and `noise_indicators` for terms that reduce an article's signal confidence.

---

## Usage

```bash
# Collect articles from all RSS feeds
python -m src.main collect

# Classify all unclassified articles
python -m src.main classify

# Generate report for current week
python -m src.main report

# Generate report for a specific week
python -m src.main report --week 2026-20

# Full weekly pipeline: collect → classify → report
python -m src.main run-weekly

# Show database statistics
python -m src.main status
```

Reports are saved to `reports/weekly_career_brief_YYYY-WW.md`.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Example Report Structure

```markdown
# Weekly Career Intelligence Brief – 2026-20

## 1. Executive Summary
Week 2026-20 produced 3 strong signals and 7 weak signals.
Key activity in: robotics, functional_safety, adas.
Notable companies: NEURA Robotics, Bosch, NVIDIA.

## 2. Strong Signals
### NEURA Robotics Announces ISO 26262-Compliant Humanoid Safety Stack
- Development: NEURA Robotics has published a safety-certified motion control …
- Companies involved: NEURA Robotics
- Region: germany
- Industry domain: robotics, functional_safety
- Technology signal: ROS2, ISO 26262, fault injection
- Career relevance: Directly relevant to functional safety, safety testing skills
- Confidence level: high
- Relevance score: 9.2 / 10
- Recommended action: study_and_apply

## 3. Weak Signals / Watchlist
- **Dassault Systèmes Expands MBSE Platform for Robotics** …

## 4. Skill Priority Update
| Skill | Current Priority | Change | Reason | Recommended Weekly Effort |
|---|---|---|---|---|
| ROS2 | high | ↑ | Signals: ros2, humanoid | 5 h |
| SOTIF / ISO/PAS 8800 | medium | → | No new signals this week | 1 h |

## 5. Recommended Learning Plan for Next Week
- 5 h: Raspberry Pi / ROS2 implementation
- 4 h: C++20 safety logic and GoogleTest
- 3 h: AI monitoring: confidence, latency, stale data
…

## 6. Career Positioning Advice
Robotics activity is strong. Emphasize ROS2 and safety-supervised robotics …

## 7. Risks and Hype to Ignore
- Generic GenAI / chatbot news …

## 8. Source List
- [NEURA Robotics Safety Stack](https://…) — The Robot Report (2026-05-12)
```

---

## Suggested Additional RSS Sources

| Source | URL | Category |
|---|---|---|
| Autocar | `https://www.autocar.co.uk/rss` | automotive |
| ISO News | `https://www.iso.org/news.atom` | standards |
| NHTSA News | `https://www.nhtsa.gov/rss` | automotive / safety |
| ROS Discourse | `https://discourse.ros.org/latest.rss` | robotics |
| Robotics Tomorrow | `https://www.roboticstomorrow.com/rss` | robotics |
| Automotive World | `https://www.automotiveworld.com/feed/` | automotive |
| SDxCentral | `https://www.sdxcentral.com/feed/` | software / SDV |
| Japan Automotive Daily | add when available | japan / automotive |

---

## Limitations

- This tool is for personal career intelligence, **not financial advice**.
- It does not guarantee job-market predictions.
- News analysis may be incomplete or biased depending on the configured RSS sources.
- Rule-based classification relies on keyword matching and will miss nuanced signals.
- **Human review is required before changing career direction.**
- LLM integration, if added, should provide structured analysis but not final decisions.
- RSS feeds may change URLs or stop publishing without notice; verify periodically.

---

## Future Extensions

- **LLM classifier**: plug in an Anthropic or OpenAI call via the `LLMClassifier` interface
- **Job market signals**: scrape LinkedIn / Indeed job postings for role trend analysis
- **GitHub activity tracker**: monitor starred repos and commit activity of key organizations
- **Company press release monitor**: targeted scraping of Bosch, NEURA, NVIDIA newsrooms
- **Email digest**: auto-send the weekly Markdown report as a formatted email
- **Skill gap analysis**: compare current CV skill claims against job posting requirements
- **Multi-language sources**: German/Japanese RSS feeds for region-specific signals
- **Scheduling**: run `collect → classify → report` automatically via cron or a task scheduler

---

_Built as a personal career decision-support tool. Not affiliated with any company listed._
