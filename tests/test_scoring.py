"""Tests for relevance scoring logic in src/score_relevance.py."""

import pytest
from src.score_relevance import (
    _domain_score,
    _region_score,
    _skill_score,
    _career_impact_score,
    _actionability_score,
    score_article,
    WEIGHTS,
    WEIGHTS_EXTERNAL_TRANSITION,
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
# Source reliability — tier-based scoring
# ---------------------------------------------------------------------------

class TestSourceReliability:
    from src.score_relevance import _source_reliability_score

    def _art(self, source_name: str) -> dict:
        return {"source_name": source_name}

    def test_ieee_scores_highest(self) -> None:
        from src.score_relevance import _source_reliability_score, SOURCE_TIERS
        score = _source_reliability_score({}, self._art("IEEE Spectrum"))
        assert score >= 0.95

    def test_reuters_scores_high(self) -> None:
        from src.score_relevance import _source_reliability_score
        score = _source_reliability_score({}, self._art("Reuters Technology"))
        assert score >= 0.90

    def test_techcrunch_scores_lower(self) -> None:
        from src.score_relevance import _source_reliability_score
        score = _source_reliability_score({}, self._art("TechCrunch AI"))
        assert score <= 0.70

    def test_electrek_scores_lower_than_ieee(self) -> None:
        from src.score_relevance import _source_reliability_score
        ieee = _source_reliability_score({}, self._art("IEEE Spectrum"))
        electrek = _source_reliability_score({}, self._art("Electrek"))
        assert ieee > electrek

    def test_unknown_source_falls_back_to_feed_score(self) -> None:
        from src.score_relevance import _source_reliability_score
        score = _source_reliability_score(
            {"source_reliability": 0.77}, self._art("SomeUnknownBlog")
        )
        assert score == 0.77

    def test_no_article_uses_feed_score(self) -> None:
        from src.score_relevance import _source_reliability_score
        score = _source_reliability_score({"source_reliability": 0.80})
        assert score == 0.80


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
        expected = {"domain", "skill", "region", "career_impact",
                    "source_reliability", "total"}
        assert expected <= scores.keys()
        assert "company" not in scores  # company relevance removed

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

    def test_actionability_score_in_result(self) -> None:
        cls = make_cls()
        scores = score_article(self._article, cls, {}, {}, {})
        assert "actionability" in scores
        assert 0.0 <= scores["actionability"] <= 10.0

    def test_external_transition_mode_weights_sum_to_one(self) -> None:
        w = WEIGHTS_EXTERNAL_TRANSITION
        total = sum(v for v in w.values())
        assert abs(total - 1.0) < 1e-9

    def test_default_mode_weights_sum_to_one(self) -> None:
        w = WEIGHTS
        total = sum(v for v in w.values())
        assert abs(total - 1.0) < 1e-9

    def test_external_transition_mode_scores_germany_higher(self) -> None:
        cls_de = make_cls(industries=["functional_safety"], regions=["germany"],
                          technologies=["iso 26262"], source_reliability=0.85)
        cls_us = make_cls(industries=["functional_safety"], regions=["usa"],
                          technologies=["iso 26262"], source_reliability=0.85)
        art = {"id": 1, "title": "Safety job opening", "summary": "We are hiring safety engineers"}
        score_de = score_article(art, cls_de, {}, {}, {}, career_mode="external_transition")
        score_us = score_article(art, cls_us, {}, {}, {}, career_mode="external_transition")
        assert score_de["total"] > score_us["total"]

    def test_bosch_japan_not_dominant(self) -> None:
        # Bosch Japan article should score below a safety job opening in Germany
        art_japan = {"id": 1, "title": "Bosch Japan opens new office in Tokyo", "summary": "Bosch expands Japan operations"}
        art_job = {"id": 2, "title": "Safety architect vacancy Germany", "summary": "We are hiring functional safety architect ISO 26262"}
        cls_japan = make_cls(industries=["automotive"], regions=["japan"], companies=["Bosch"])
        cls_job = make_cls(industries=["functional_safety"], regions=["germany"],
                           technologies=["iso 26262", "safety architecture"])
        score_japan = score_article(art_japan, cls_japan, {}, {}, {}, career_mode="external_transition")
        score_job = score_article(art_job, cls_job, {}, {}, {}, career_mode="external_transition")
        assert score_job["total"] >= score_japan["total"]


# ---------------------------------------------------------------------------
# Actionability score
# ---------------------------------------------------------------------------

class TestActionabilityScore:
    def _art(self, title: str, summary: str = "") -> dict:
        return {"id": 1, "title": title, "summary": summary}

    def test_hiring_signal_scores_high(self) -> None:
        art = self._art("We are hiring functional safety engineers in Munich")
        cls = make_cls(industries=["functional_safety"], regions=["germany"])
        score = _actionability_score(art, cls)
        assert score >= 0.7

    def test_generic_chatgpt_news_scores_low(self) -> None:
        art = self._art("ChatGPT viral marketing campaign drives brand engagement")
        cls = make_cls(industries=["ai"])
        score = _actionability_score(art, cls)
        assert score <= 0.3

    def test_safety_standard_event_scores_medium(self) -> None:
        art = self._art("ISO 13849 update: new requirements for machinery safety certification")
        cls = make_cls(industries=["functional_safety"])
        score = _actionability_score(art, cls)
        assert score >= 0.4

    def test_restructuring_signal_scores_medium_plus(self) -> None:
        art = self._art("Bosch announces restructuring and headcount reduction in automotive division",
                        "Major layoffs announced in Germany engineering teams")
        cls = make_cls(industries=["automotive"], regions=["germany"])
        score = _actionability_score(art, cls)
        assert score >= 0.35

    def test_humanoid_demo_without_safety_scores_low(self) -> None:
        art = self._art("Amazing humanoid demo wows investors at CES")
        cls = make_cls(industries=["robotics"])
        score = _actionability_score(art, cls)
        assert score <= 0.4

    def test_germany_region_boosts_score(self) -> None:
        art = self._art("Safety engineer job opening in Stuttgart")
        cls_de = make_cls(industries=["functional_safety"], regions=["germany"])
        cls_us = make_cls(industries=["functional_safety"], regions=["usa"])
        assert _actionability_score(art, cls_de) > _actionability_score(art, cls_us)
