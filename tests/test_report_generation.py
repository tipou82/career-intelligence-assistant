"""Tests for Markdown report generation helpers in src/generate_weekly_report.py."""

import json
import pytest
from src.generate_weekly_report import (
    _build_career_advice,
    _build_career_actions_section,
    _build_executive_summary,
    _build_learning_allocation,
    _build_market_fit_section,
    _build_risks_section,
    _build_skill_table,
    _build_source_list,
    _build_strong_signals,
    _build_weak_signals,
    _format_signal_entry,
    _load_career_mode,
    _load_weekly_hours_cap,
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


# Minimal skill matrix using the new 3D format (int priority, urgency, required_depth)
MINIMAL_SKILL_MATRIX = {
    "skills": [
        {
            "name": "ROS2",
            "priority": 5,
            "urgency": 5,
            "required_depth": 4,
            "weekly_hours_baseline": 5,
            "group": "deep_focus",
            "learning_task": "ROS2 nodes on Raspberry Pi",
            "triggers": {"increase": ["ros2", "humanoid", "physical ai"], "decrease": []},
        },
        {
            "name": "C++20 and safety logic",
            "priority": 5,
            "urgency": 5,
            "required_depth": 5,
            "weekly_hours_baseline": 4,
            "group": "deep_focus",
            "learning_task": "C++20 safety logic and GoogleTest",
            "triggers": {"increase": ["c++20", "embedded software"], "decrease": []},
        },
        {
            "name": "ISO 13849 and CMSE",
            "priority": 4,
            "urgency": 4,
            "required_depth": 4,
            "weekly_hours_baseline": 3,
            "group": "serious",
            "learning_task": "Safety function, PLr, Categories, MTTFd/DCavg/CCF",
            "triggers": {"increase": ["iso 13849", "performance level", "safety function"], "decrease": []},
        },
        {
            "name": "MBSE and SysML2",
            "priority": 3,
            "urgency": 3,
            "required_depth": 3,
            "weekly_hours_baseline": 2,
            "group": "lightweight",
            "learning_task": "Mermaid diagrams and lightweight SysML2",
            "triggers": {"increase": ["mbse", "sysml", "dassault"], "decrease": []},
        },
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

    def test_weak_below_threshold_excluded(self) -> None:
        # Score 2.0 is below the weak threshold (4.5)
        articles = [make_article(signal_strength="weak", relevance_score=2.0)]
        assert _build_weak_signals(articles) == []

    def test_weak_above_threshold_included(self) -> None:
        articles = [make_article(signal_strength="weak", relevance_score=5.0)]
        assert len(_build_weak_signals(articles)) == 1

    def test_empty_input_returns_empty(self) -> None:
        assert _build_strong_signals([]) == []
        assert _build_weak_signals([]) == []

    def test_strong_signal_included_regardless_of_score(self) -> None:
        # signal_strength is set by classifier; report trusts it
        articles = [make_article(signal_strength="strong", relevance_score=6.5)]
        assert len(_build_strong_signals(articles)) == 1


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
# Skill table — 7-column format with 3D scoring
# ---------------------------------------------------------------------------

class TestSkillTable:
    def test_all_skills_present_in_table(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        assert "ROS2" in table
        assert "C++20 and safety logic" in table
        assert "ISO 13849 and CMSE" in table

    def test_header_has_three_score_columns(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        assert "Priority" in table
        assert "Urgency" in table
        assert "Req. Depth" in table

    def test_scores_show_out_of_five(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        assert "5/5" in table  # ROS2 priority=5, urgency=5

    def test_group_separator_rows_present(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        assert "Deep Focus" in table
        assert "Serious" in table
        assert "Lightweight" in table

    def test_trigger_causes_up_arrow(self) -> None:
        article = make_article(technologies=["ros2"])
        table = _build_skill_table([article], MINIMAL_SKILL_MATRIX)
        lines = [l for l in table.splitlines() if "ROS2" in l]
        assert any("↑" in line for line in lines)

    def test_no_trigger_causes_right_arrow(self) -> None:
        table = _build_skill_table([], MINIMAL_SKILL_MATRIX)
        lines = [l for l in table.splitlines() if "ROS2" in l]
        assert any("→" in line for line in lines)

    def test_iso13849_trigger_on_machinery_article(self) -> None:
        article = make_article(skills=["iso 13849", "performance level"])
        table = _build_skill_table([article], MINIMAL_SKILL_MATRIX)
        lines = [l for l in table.splitlines() if "ISO 13849" in l]
        assert any("↑" in line for line in lines)

    def test_mbse_trigger_on_dassault_article(self) -> None:
        article = make_article(technologies=["sysml", "dassault"])
        table = _build_skill_table([article], MINIMAL_SKILL_MATRIX)
        lines = [l for l in table.splitlines() if "MBSE" in l]
        assert any("↑" in line for line in lines)


# ---------------------------------------------------------------------------
# Learning allocation — grouped format
# ---------------------------------------------------------------------------

class TestLearningAllocation:
    def test_contains_group_headers(self) -> None:
        alloc = _build_learning_allocation([], MINIMAL_SKILL_MATRIX)
        assert "Deep Focus" in alloc
        assert "Serious" in alloc

    def test_contains_learning_tasks(self) -> None:
        alloc = _build_learning_allocation([], MINIMAL_SKILL_MATRIX)
        assert "ROS2 nodes on Raspberry Pi" in alloc
        assert "C++20 safety logic and GoogleTest" in alloc

    def test_hours_shown(self) -> None:
        alloc = _build_learning_allocation([], MINIMAL_SKILL_MATRIX)
        assert " h:" in alloc

    def test_total_hours_shown(self) -> None:
        alloc = _build_learning_allocation([], MINIMAL_SKILL_MATRIX)
        assert "total" in alloc.lower() or "cap" in alloc.lower()

    def test_triggered_skill_gets_bonus_hour(self) -> None:
        article = make_article(technologies=["ros2"])
        alloc_triggered = _build_learning_allocation([article], MINIMAL_SKILL_MATRIX)
        alloc_base = _build_learning_allocation([], MINIMAL_SKILL_MATRIX)
        # Triggered allocation should mention more hours for ROS2 (5+1=6 vs 5)
        assert "6 h:" in alloc_triggered
        assert "5 h:" in alloc_base  # base is 5h without trigger

    def test_skill_matrix_loading_fields(self) -> None:
        # All required new fields must be present in MINIMAL_SKILL_MATRIX
        for skill in MINIMAL_SKILL_MATRIX["skills"]:
            assert "priority" in skill and isinstance(skill["priority"], int)
            assert "urgency" in skill and isinstance(skill["urgency"], int)
            assert "required_depth" in skill and isinstance(skill["required_depth"], int)
            assert "weekly_hours_baseline" in skill
            assert "group" in skill
            assert "triggers" in skill


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


# ---------------------------------------------------------------------------
# External transition mode
# ---------------------------------------------------------------------------

class TestCareerMode:
    def test_career_mode_loads_from_yaml(self) -> None:
        mode = _load_career_mode()
        assert mode in ("external_transition", "default")

    def test_weekly_hours_cap_loads(self) -> None:
        cap = _load_weekly_hours_cap()
        assert 10 <= cap <= 40

    def test_learning_allocation_respects_cap(self) -> None:
        cap = 12
        alloc = _build_learning_allocation([], MINIMAL_SKILL_MATRIX, hours_cap=cap)
        # Extract total from the note line
        import re
        match = re.search(r"total: ~(\d+) h", alloc)
        if match:
            total = int(match.group(1))
            assert total <= cap

    def test_learning_allocation_never_exceeds_20h(self) -> None:
        # With default cap (20h), total must not exceed it
        big_matrix = {
            "skills": [
                {"name": f"Skill{i}", "priority": 5, "urgency": 5, "required_depth": 5,
                 "weekly_hours_baseline": 5, "group": "deep_focus",
                 "learning_task": "Task", "triggers": {"increase": [], "decrease": []}}
                for i in range(10)
            ]
        }
        alloc = _build_learning_allocation([], big_matrix, hours_cap=20)
        import re
        match = re.search(r"total: ~(\d+) h", alloc)
        if match:
            assert int(match.group(1)) <= 20

    def test_career_actions_section_in_external_mode(self) -> None:
        articles = [make_article(signal_strength="strong")]
        text = _build_career_actions_section(articles, MINIMAL_SKILL_MATRIX, "external_transition")
        assert "Role Cluster" in text or "Action Plan" in text or "Network" in text

    def test_career_actions_empty_in_default_mode(self) -> None:
        articles = [make_article()]
        text = _build_career_actions_section(articles, MINIMAL_SKILL_MATRIX, "default")
        assert text == ""

    def test_market_fit_section_in_external_mode(self) -> None:
        articles = [make_article(industries=["functional_safety"], technologies=["iso 26262"])]
        text = _build_market_fit_section(articles, "external_transition")
        assert "Automotive" in text or "Market Fit" in text or "fit" in text.lower()

    def test_market_fit_empty_in_default_mode(self) -> None:
        text = _build_market_fit_section([], "default")
        assert text == ""

    def test_weak_signals_sorted_by_actionability(self) -> None:
        # Article with hiring signal should rank above generic article
        high_act = make_article(
            title="Functional safety engineer vacancy Germany",
            summary="We are hiring ISO 26262 experts",
            signal_strength="weak", relevance_score=5.0
        )
        low_act = make_article(
            title="Generic AI news", summary="ChatGPT gets new features",
            signal_strength="weak", relevance_score=5.5
        )
        # high_act has higher actionability despite lower relevance_score
        from src.score_relevance import _actionability_score
        cls = {"industries": ["functional_safety"], "regions": ["germany"],
               "technologies": [], "skills": []}
        act_high = _actionability_score(high_act, cls)
        act_low = _actionability_score(low_act, {})
        assert act_high > act_low
