"""Tests for Markdown report generation helpers in src/generate_weekly_report.py."""

import json
import pytest
from src.generate_weekly_report import (
    _build_career_advice,
    _build_executive_summary,
    _build_risks_section,
    _build_skill_table,
    _build_source_list,
    _build_strong_signals,
    _build_weak_signals,
    _format_signal_entry,
    get_week_label,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_article(
    title: str = "Test Article",
    summary: str = "Test summary about ROS2 and functional safety in Germany.",
    source_name: str = "IEEE Spectrum",
    published_date: str = "2026-05-12T00:00:00",
    url: str = "https://example.com/test",
    relevance_score: float = 8.5,
    signal_strength: str = "strong",
    confidence_level: str = "high",
    recommended_action: str = "study_and_apply",
    industries: list | None = None,
    technologies: list | None = None,
    companies: list | None = None,
    regions: list | None = None,
    skills: list | None = None,
) -> dict:
    cls = {
        "industries": industries or ["robotics", "automotive"],
        "technologies": technologies or ["ros2", "functional safety"],
        "companies": companies or ["Bosch"],
        "regions": regions or ["germany"],
        "skills": skills or ["safety testing"],
        "source_reliability": 0.9,
    }
    return {
        "id": 1,
        "title": title,
        "summary": summary,
        "source_name": source_name,
        "published_date": published_date,
        "url": url,
        "relevance_score": relevance_score,
        "signal_strength": signal_strength,
        "confidence_level": confidence_level,
        "recommended_action": recommended_action,
        "classification": json.dumps(cls),
    }


MINIMAL_SKILL_MATRIX = {
    "skills": [
        {"name": "ROS2", "priority": "high", "weekly_hours": 5,
         "learning_task": "ROS2 nodes on Raspberry Pi",
         "triggers": {"increase": ["ros2", "humanoid"], "decrease": []}},
        {"name": "C++20 and testing", "priority": "high", "weekly_hours": 4,
         "learning_task": "C++20 safety logic and GoogleTest",
         "triggers": {"increase": ["c++20"], "decrease": []}},
    ]
}


# ---------------------------------------------------------------------------
# Week label
# ---------------------------------------------------------------------------

class TestWeekLabel:
    def test_current_returns_year_week(self) -> None:
        label = get_week_label("current")
        year, week = label.split("-")
        assert year.isdigit() and week.isdigit()

    def test_none_same_as_current(self) -> None:
        assert get_week_label(None) == get_week_label("current")

    def test_explicit_passthrough(self) -> None:
        assert get_week_label("2026-20") == "2026-20"

    def test_last_differs_from_current(self) -> None:
        assert get_week_label("last") != get_week_label("current")


# ---------------------------------------------------------------------------
# Signal filtering
# ---------------------------------------------------------------------------

class TestSignalFiltering:
    def _articles(self) -> list:
        return [
            make_article(signal_strength="strong", relevance_score=8.5),
            make_article(signal_strength="weak", relevance_score=5.0),
            make_article(signal_strength="noise", relevance_score=1.0),
        ]

    def test_only_strong_signals_returned(self) -> None:
        result = _build_strong_signals(self._articles())
        assert all(a["signal_strength"] == "strong" for a in result)

    def test_only_weak_signals_returned(self) -> None:
        result = _build_weak_signals(self._articles())
        assert all(a["signal_strength"] == "weak" for a in result)

    def test_strong_below_threshold_excluded(self) -> None:
        articles = [make_article(signal_strength="strong", relevance_score=5.0)]
        assert _build_strong_signals(articles) == []

    def test_weak_below_threshold_excluded(self) -> None:
        articles = [make_article(signal_strength="weak", relevance_score=2.0)]
        assert _build_weak_signals(articles) == []

    def test_empty_input_returns_empty(self) -> None:
        assert _build_strong_signals([]) == []
        assert _build_weak_signals([]) == []


# ---------------------------------------------------------------------------
# Signal entry formatting
# ---------------------------------------------------------------------------

class TestSignalEntry:
    def test_contains_title(self) -> None:
        a = make_article(title="NEURA Robotics Safety Framework")
        assert "NEURA Robotics Safety Framework" in _format_signal_entry(a)

    def test_contains_required_labels(self) -> None:
        entry = _format_signal_entry(make_article())
        for label in ("Development", "Companies involved", "Region",
                      "Industry domain", "Technology signal",
                      "Confidence level", "Recommended action"):
            assert label in entry

    def test_url_included_when_present(self) -> None:
        a = make_article(url="https://example.com/article")
        assert "https://example.com/article" in _format_signal_entry(a)

    def test_no_url_line_when_missing(self) -> None:
        a = make_article(url="")
        assert "URL" not in _format_signal_entry(a)


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

class TestExecutiveSummary:
    def test_no_signals_mentions_quiet(self) -> None:
        text = _build_executive_summary([], [], "2026-20")
        assert "no strong" in text.lower() or "no major" in text.lower() or "0" in text

    def test_with_signals_shows_count(self) -> None:
        articles = [make_article(), make_article()]
        text = _build_executive_summary(articles, [], "2026-20")
        assert "2" in text

    def test_week_label_appears(self) -> None:
        text = _build_executive_summary([], [], "2026-20")
        assert "2026-20" in text


# ---------------------------------------------------------------------------
# Skill table
# ---------------------------------------------------------------------------

class TestSkillTable:
    def test_all_skills_present_in_table(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        assert "ROS2" in table
        assert "C++20 and testing" in table

    def test_header_row_present(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        assert "Skill" in table
        assert "Current Priority" in table

    def test_trigger_causes_up_arrow(self) -> None:
        # Article with ros2 signal should cause ROS2 row to show ↑
        article = make_article(technologies=["ros2"])
        table = _build_skill_table([article], MINIMAL_SKILL_MATRIX)
        lines = [l for l in table.splitlines() if "ROS2" in l]
        assert any("↑" in line for line in lines)

    def test_no_trigger_causes_right_arrow(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        lines = [l for l in table.splitlines() if "ROS2" in l]
        assert any("→" in line for line in lines)


# ---------------------------------------------------------------------------
# Source list
# ---------------------------------------------------------------------------

class TestSourceList:
    def test_article_title_in_list(self) -> None:
        articles = [make_article(title="Bosch Announces ROS2 Platform")]
        assert "Bosch Announces ROS2 Platform" in _build_source_list(articles)

    def test_empty_returns_placeholder(self) -> None:
        assert "_No sources" in _build_source_list([])

    def test_duplicate_urls_deduplicated(self) -> None:
        a = make_article(url="https://example.com/dup")
        result = _build_source_list([a, a])
        assert result.count("https://example.com/dup") == 1


# ---------------------------------------------------------------------------
# Career advice
# ---------------------------------------------------------------------------

class TestCareerAdvice:
    def test_empty_signals_returns_default(self) -> None:
        advice = _build_career_advice([])
        assert "ros2" in advice.lower() or "c++20" in advice.lower() or "current" in advice.lower()

    def test_robotics_signal_mentioned(self) -> None:
        a = make_article(industries=["robotics"], technologies=["ros2"])
        advice = _build_career_advice([a])
        assert "ros2" in advice.lower() or "robotics" in advice.lower()


# ---------------------------------------------------------------------------
# Risks section
# ---------------------------------------------------------------------------

class TestRisksSection:
    def test_contains_standard_warnings(self) -> None:
        text = _build_risks_section([])
        assert "GenAI" in text or "chatbot" in text.lower()

    def test_noise_titles_listed(self) -> None:
        noise = [make_article(title="Top 10 ChatGPT Prompts for Marketers")]
        text = _build_risks_section(noise)
        assert "Top 10 ChatGPT" in text
