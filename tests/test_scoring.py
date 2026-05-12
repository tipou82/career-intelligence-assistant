"""Tests for relevance scoring logic in src/score_relevance.py."""

import pytest
from src.score_relevance import (
    _company_score,
    _domain_score,
    _region_score,
    _skill_score,
    _career_impact_score,
    score_article,
)


def make_cls(**kwargs: object) -> dict:
    """Build a classification dict, merging kwargs into safe defaults."""
    defaults: dict = {
        "industries": [],
        "regions": [],
        "companies": [],
        "technologies": [],
        "skills": [],
        "confidence_level": "medium",
        "source_reliability": 0.7,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Domain score
# ---------------------------------------------------------------------------

class TestDomainScore:
    def test_known_high_value_industry(self) -> None:
        assert _domain_score(make_cls(industries=["robotics"])) == 1.0

    def test_unknown_industry_scores_low(self) -> None:
        assert _domain_score(make_cls(industries=["entertainment"])) == 0.05

    def test_empty_industries_scores_zero(self) -> None:
        assert _domain_score(make_cls()) == 0.0

    def test_best_industry_wins(self) -> None:
        assert _domain_score(make_cls(industries=["robotics", "entertainment"])) == 1.0

    def test_embedded_scores_high(self) -> None:
        assert _domain_score(make_cls(industries=["embedded"])) == 0.9

    def test_machinery_safety_scores_high(self) -> None:
        assert _domain_score(make_cls(industries=["machinery_safety"])) == 0.9

    def test_physical_ai_scores_high(self) -> None:
        assert _domain_score(make_cls(industries=["physical_ai"])) == 0.9


# ---------------------------------------------------------------------------
# Skill score
# ---------------------------------------------------------------------------

class TestSkillScore:
    def test_ros2_scores_max(self) -> None:
        assert _skill_score(make_cls(technologies=["ros2"])) == 1.0

    def test_iso26262_scores_max(self) -> None:
        assert _skill_score(make_cls(skills=["iso 26262"])) == 1.0

    def test_unknown_skill_scores_low(self) -> None:
        assert _skill_score(make_cls(skills=["powerpoint"])) == 0.05

    def test_empty_returns_zero(self) -> None:
        assert _skill_score(make_cls()) == 0.0

    def test_best_skill_wins(self) -> None:
        assert _skill_score(make_cls(technologies=["ros2", "embedded linux"])) == 1.0

    def test_skills_and_technologies_combined(self) -> None:
        assert _skill_score(make_cls(technologies=[], skills=["sotif"])) == 1.0

    def test_iso13849_scores_high(self) -> None:
        assert _skill_score(make_cls(skills=["iso 13849"])) == 1.0

    def test_performance_level_scores_high(self) -> None:
        score = _skill_score(make_cls(skills=["performance level"]))
        assert score >= 0.9

    def test_fault_injection_scores_high(self) -> None:
        score = _skill_score(make_cls(technologies=["fault injection"]))
        assert score >= 0.9

    def test_confidence_monitoring_scores_high(self) -> None:
        score = _skill_score(make_cls(skills=["confidence monitoring"]))
        assert score == 1.0

    def test_safety_function_scores_high(self) -> None:
        score = _skill_score(make_cls(skills=["safety function"]))
        assert score >= 0.9

    def test_qnx_scores_high(self) -> None:
        assert _skill_score(make_cls(technologies=["qnx"])) == 0.9


# ---------------------------------------------------------------------------
# Company score
# ---------------------------------------------------------------------------

class TestCompanyScore:
    def test_tier1_company_max(self) -> None:
        assert _company_score(make_cls(companies=["Bosch"])) == 1.0

    def test_tier1_case_insensitive(self) -> None:
        assert _company_score(make_cls(companies=["bosch"])) == 1.0

    def test_tier2_company_medium(self) -> None:
        assert _company_score(make_cls(companies=["Unitree"])) == 0.6

    def test_unknown_company_low(self) -> None:
        assert _company_score(make_cls(companies=["SomeUnknownCorp"])) == 0.15

    def test_no_company_zero(self) -> None:
        assert _company_score(make_cls()) == 0.0

    def test_tier1_beats_tier2(self) -> None:
        assert _company_score(make_cls(companies=["Bosch", "Unitree"])) == 1.0

    def test_pilz_is_tier1(self) -> None:
        # Pilz: key machinery safety company
        assert _company_score(make_cls(companies=["Pilz"])) == 1.0

    def test_kuka_is_tier1(self) -> None:
        assert _company_score(make_cls(companies=["KUKA"])) == 1.0


# ---------------------------------------------------------------------------
# Region score
# ---------------------------------------------------------------------------

class TestRegionScore:
    def test_germany_max(self) -> None:
        assert _region_score(make_cls(regions=["germany"])) == 1.0

    def test_japan_high(self) -> None:
        assert _region_score(make_cls(regions=["japan"])) == 0.9

    def test_unknown_region_low(self) -> None:
        assert _region_score(make_cls(regions=["antarctica"])) == 0.15

    def test_no_region_partial_credit(self) -> None:
        assert _region_score(make_cls()) == 0.3

    def test_best_region_wins(self) -> None:
        assert _region_score(make_cls(regions=["germany", "antarctica"])) == 1.0


# ---------------------------------------------------------------------------
# Career impact score
# ---------------------------------------------------------------------------

class TestCareerImpactScore:
    def test_robotics_ros2_pair_max_impact(self) -> None:
        cls = make_cls(industries=["robotics"], technologies=["ros2"])
        assert _career_impact_score(cls) == 1.0

    def test_robotics_iso13849_pair_max_impact(self) -> None:
        cls = make_cls(industries=["robotics"], skills=["iso 13849"])
        assert _career_impact_score(cls) == 1.0

    def test_adas_sotif_pair_max_impact(self) -> None:
        cls = make_cls(industries=["adas"], technologies=["sotif"])
        assert _career_impact_score(cls) == 1.0

    def test_ai_fault_injection_pair_max_impact(self) -> None:
        cls = make_cls(industries=["ai"], skills=["fault injection"])
        assert _career_impact_score(cls) == 1.0

    def test_generic_industry_lower_impact(self) -> None:
        cls = make_cls(industries=["ai"])
        assert _career_impact_score(cls) == 0.5

    def test_empty_minimal_impact(self) -> None:
        cls = make_cls()
        assert _career_impact_score(cls) == 0.2


# ---------------------------------------------------------------------------
# Full score_article
# ---------------------------------------------------------------------------

class TestScoreArticle:
    _article = {"id": 1, "title": "Test", "summary": ""}

    def test_high_relevance_above_seven(self) -> None:
        cls = make_cls(
            industries=["robotics", "automotive"],
            regions=["germany"],
            companies=["Bosch"],
            technologies=["ros2", "functional safety"],
            skills=["safety testing"],
            source_reliability=0.9,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] >= 7.0

    def test_low_relevance_below_four(self) -> None:
        cls = make_cls(
            industries=["entertainment"],
            regions=[],
            companies=[],
            technologies=[],
            skills=[],
            source_reliability=0.3,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] < 4.0

    def test_score_within_0_to_10(self) -> None:
        cls = make_cls(
            industries=["automotive"],
            regions=["europe"],
            companies=["Tesla"],
            technologies=["sotif"],
            skills=["functional safety"],
            source_reliability=0.8,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert 0.0 <= scores["total"] <= 10.0

    def test_score_dict_has_all_components(self) -> None:
        cls = make_cls()
        scores = score_article(self._article, cls, {}, {}, {})
        expected = {"domain", "skill", "company", "region", "career_impact",
                    "source_reliability", "total"}
        assert expected <= scores.keys()

    def test_high_impact_pair_boosts_score(self) -> None:
        cls = make_cls(industries=["robotics"], technologies=["ros2"], source_reliability=0.85)
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["career_impact"] == 10.0

    def test_score_capped_at_ten(self) -> None:
        cls = make_cls(
            industries=["robotics"],
            regions=["germany"],
            companies=["Bosch"],
            technologies=["ros2", "iso/pas 8800", "sotif"],
            skills=["functional safety"],
            source_reliability=1.0,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] <= 10.0

    def test_iso13849_machinery_robotics_scores_high(self) -> None:
        cls = make_cls(
            industries=["robotics"],
            regions=["germany"],
            companies=["Pilz"],
            skills=["iso 13849", "safety function", "performance level"],
            source_reliability=0.85,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] >= 7.0

    def test_ai_monitoring_scores_high(self) -> None:
        cls = make_cls(
            industries=["ai", "embedded"],
            regions=["global"],
            technologies=["confidence monitoring", "fault injection"],
            skills=["ai perception monitoring"],
            source_reliability=0.8,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] >= 6.0
