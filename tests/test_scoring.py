"""Tests for relevance scoring logic in src/score_relevance.py (cultural-PM profile)."""

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
        assert _domain_score(make_cls(industries=["cultural_management"])) == 1.0

    def test_education_programs_scores_max(self) -> None:
        assert _domain_score(make_cls(industries=["education_programs"])) == 1.0

    def test_unknown_industry_scores_low(self) -> None:
        assert _domain_score(make_cls(industries=["automotive"])) == 0.05

    def test_empty_industries_scores_zero(self) -> None:
        assert _domain_score(make_cls()) == 0.0

    def test_best_industry_wins(self) -> None:
        assert _domain_score(make_cls(industries=["cultural_management", "automotive"])) == 1.0

    def test_event_production_scores_high(self) -> None:
        assert _domain_score(make_cls(industries=["event_production"])) == 0.95

    def test_music_classical_scores_high(self) -> None:
        assert _domain_score(make_cls(industries=["music_classical"])) == 0.9

    def test_museum_lower_than_core(self) -> None:
        score = _domain_score(make_cls(industries=["museum_exhibition"]))
        assert score < _domain_score(make_cls(industries=["cultural_management"]))


# ---------------------------------------------------------------------------
# Skill score
# ---------------------------------------------------------------------------

class TestSkillScore:
    def test_kulturmanagement_scores_max(self) -> None:
        assert _skill_score(make_cls(skills=["kulturmanagement"])) == 1.0

    def test_musikvermittlung_scores_max(self) -> None:
        assert _skill_score(make_cls(skills=["musikvermittlung"])) == 1.0

    def test_bildungsreferent_scores_max(self) -> None:
        assert _skill_score(make_cls(skills=["bildungsreferent"])) == 1.0

    def test_veranstaltungsmanagement_scores_max(self) -> None:
        assert _skill_score(make_cls(skills=["veranstaltungsmanagement"])) == 1.0

    def test_unknown_skill_scores_low(self) -> None:
        assert _skill_score(make_cls(skills=["iso 26262"])) == 0.05

    def test_empty_returns_zero(self) -> None:
        assert _skill_score(make_cls()) == 0.0

    def test_best_skill_wins(self) -> None:
        # An unknown skill alongside a top one should still return the top score
        assert _skill_score(make_cls(skills=["musikvermittlung", "powerpoint"])) == 1.0

    def test_scrum_master_scores_high(self) -> None:
        score = _skill_score(make_cls(skills=["scrum master"]))
        assert score >= 0.85

    def test_pressearbeit_scores_high(self) -> None:
        score = _skill_score(make_cls(skills=["pressearbeit"]))
        assert score >= 0.85

    def test_audience_development_scores_high(self) -> None:
        score = _skill_score(make_cls(skills=["audience development"]))
        assert score >= 0.85

    def test_chinese_term_normalised(self) -> None:
        # 项目管理 → "project management"
        assert _skill_score(make_cls(skills=["项目管理"])) == 1.0


# ---------------------------------------------------------------------------
# Source reliability — tier-based scoring
# ---------------------------------------------------------------------------

class TestSourceReliability:
    from src.score_relevance import _source_reliability_score

    def _art(self, source_name: str) -> dict:
        return {"source_name": source_name}

    def test_faz_scores_highest(self) -> None:
        from src.score_relevance import _source_reliability_score
        score = _source_reliability_score({}, self._art("FAZ Feuilleton"))
        assert score >= 0.90

    def test_nmz_scores_high(self) -> None:
        from src.score_relevance import _source_reliability_score
        score = _source_reliability_score({}, self._art("nmz"))
        assert score >= 0.85

    def test_slipped_disc_scores_lower(self) -> None:
        from src.score_relevance import _source_reliability_score
        score = _source_reliability_score({}, self._art("Slipped Disc"))
        assert score <= 0.70

    def test_faz_higher_than_slipped_disc(self) -> None:
        from src.score_relevance import _source_reliability_score
        faz = _source_reliability_score({}, self._art("FAZ"))
        slipped = _source_reliability_score({}, self._art("Slipped Disc"))
        assert faz > slipped

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
    def test_stuttgart_max(self) -> None:
        assert _region_score(make_cls(regions=["stuttgart"])) == 1.0

    def test_leonberg_max(self) -> None:
        assert _region_score(make_cls(regions=["leonberg"])) == 1.0

    def test_germany_high(self) -> None:
        assert _region_score(make_cls(regions=["germany"])) == 0.9

    def test_europe_medium(self) -> None:
        assert _region_score(make_cls(regions=["europe"])) == 0.75

    def test_unknown_region_low(self) -> None:
        assert _region_score(make_cls(regions=["antarctica"])) == 0.15

    def test_no_region_partial_credit(self) -> None:
        assert _region_score(make_cls()) == 0.3

    def test_best_region_wins(self) -> None:
        assert _region_score(make_cls(regions=["stuttgart", "antarctica"])) == 1.0

    def test_stuttgart_outscores_germany(self) -> None:
        assert _region_score(make_cls(regions=["stuttgart"])) > _region_score(
            make_cls(regions=["germany"])
        )


# ---------------------------------------------------------------------------
# Career impact score
# ---------------------------------------------------------------------------

class TestCareerImpactScore:
    def test_cultural_pm_pair_max_impact(self) -> None:
        cls = make_cls(industries=["cultural_management"], skills=["projektmanagement"])
        assert _career_impact_score(cls) == 1.0

    def test_education_musikvermittlung_pair_max_impact(self) -> None:
        cls = make_cls(industries=["education_programs"], skills=["musikvermittlung"])
        assert _career_impact_score(cls) == 1.0

    def test_event_production_konzertdirektion_pair_max_impact(self) -> None:
        cls = make_cls(industries=["event_production"], skills=["konzertdirektion"])
        assert _career_impact_score(cls) == 1.0

    def test_museum_education_pair_max_impact(self) -> None:
        cls = make_cls(industries=["museum_exhibition"], skills=["museumspädagogik"])
        assert _career_impact_score(cls) == 1.0

    def test_generic_industry_lower_impact(self) -> None:
        cls = make_cls(industries=["pr_communication"])
        assert _career_impact_score(cls) == 0.65

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
            industries=["cultural_management", "education_programs"],
            regions=["stuttgart"],
            companies=["Stuttgarter Liederhalle"],
            technologies=["scrum"],
            skills=["musikvermittlung", "projektmanagement"],
            source_reliability=0.9,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] >= 7.0

    def test_low_relevance_below_four(self) -> None:
        cls = make_cls(
            industries=["automotive"],
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
            industries=["music_classical"],
            regions=["europe"],
            companies=["Berliner Philharmoniker"],
            technologies=["ticketing"],
            skills=["pressearbeit"],
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
        cls = make_cls(industries=["cultural_management"], skills=["projektmanagement"],
                       source_reliability=0.85)
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["career_impact"] == 10.0

    def test_score_capped_at_ten(self) -> None:
        cls = make_cls(
            industries=["cultural_management", "education_programs"],
            regions=["stuttgart"],
            companies=["Stuttgarter Liederhalle"],
            technologies=["scrum master"],
            skills=["musikvermittlung", "projektmanagement", "veranstaltungsmanagement"],
            source_reliability=1.0,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] <= 10.0

    def test_education_in_stuttgart_scores_high(self) -> None:
        cls = make_cls(
            industries=["education_programs"],
            regions=["stuttgart"],
            companies=["Musikhochschule Stuttgart"],
            skills=["bildungsreferent", "musikvermittlung", "kulturelle bildung"],
            source_reliability=0.85,
        )
        scores = score_article(self._article, cls, {}, {}, {})
        assert scores["total"] >= 7.0

    def test_event_production_local_scores_high(self) -> None:
        cls = make_cls(
            industries=["event_production"],
            regions=["ludwigsburg"],
            companies=["Schlossfestspiele Ludwigsburg"],
            skills=["veranstaltungsmanagement", "künstlerbetreuung"],
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

    def test_external_transition_mode_scores_stuttgart_higher(self) -> None:
        cls_stu = make_cls(industries=["cultural_management"], regions=["stuttgart"],
                           skills=["projektmanagement"], source_reliability=0.85)
        cls_global = make_cls(industries=["cultural_management"], regions=["global"],
                              skills=["projektmanagement"], source_reliability=0.85)
        art = {"id": 1, "title": "Cultural project manager opening", "summary": "We are hiring a Projektmanager Kultur"}
        score_stu = score_article(art, cls_stu, {}, {}, {}, career_mode="external_transition")
        score_global = score_article(art, cls_global, {}, {}, {}, career_mode="external_transition")
        assert score_stu["total"] > score_global["total"]

    def test_local_job_outscores_remote_news(self) -> None:
        # A local vacancy should score above a generic distant industry update
        art_local = {
            "id": 1,
            "title": "Stuttgarter Liederhalle sucht Projektmanager Kultur",
            "summary": "Wir suchen ab sofort eine Projektmanagerin Kultur in Vollzeit",
        }
        art_remote = {
            "id": 2,
            "title": "New York Philharmonic announces season",
            "summary": "The orchestra unveils a new season programme",
        }
        cls_local = make_cls(
            industries=["cultural_management"], regions=["stuttgart"],
            companies=["Stuttgarter Liederhalle"], skills=["projektmanagement"],
        )
        cls_remote = make_cls(
            industries=["music_classical"], regions=["global"],
            companies=["NY Philharmonic"],
        )
        s_local = score_article(art_local, cls_local, {}, {}, {}, career_mode="external_transition")
        s_remote = score_article(art_remote, cls_remote, {}, {}, {}, career_mode="external_transition")
        assert s_local["total"] >= s_remote["total"]


# ---------------------------------------------------------------------------
# Actionability score
# ---------------------------------------------------------------------------

class TestActionabilityScore:
    def _art(self, title: str, summary: str = "") -> dict:
        return {"id": 1, "title": title, "summary": summary}

    def test_hiring_signal_scores_high(self) -> None:
        art = self._art("Wir suchen Projektmanagerin Kultur in Stuttgart")
        cls = make_cls(industries=["cultural_management"], regions=["stuttgart"])
        score = _actionability_score(art, cls)
        assert score >= 0.7

    def test_generic_celebrity_news_scores_low(self) -> None:
        art = self._art("Celebrity gossip viral influencer scandal")
        cls = make_cls(industries=["music_classical"])
        score = _actionability_score(art, cls)
        assert score <= 0.3

    def test_funding_call_scores_medium(self) -> None:
        art = self._art("Förderaufruf Kulturelle Bildung 2026 — Antragsfrist bis Juni")
        cls = make_cls(industries=["funding_policy"], regions=["baden-württemberg"])
        score = _actionability_score(art, cls)
        assert score >= 0.4

    def test_restructuring_signal_scores_medium_plus(self) -> None:
        art = self._art(
            "Etatkürzung trifft Stuttgarter Kulturhaushalt — Stellenabbau angekündigt",
            "Die Stadt kündigt Sparmaßnahmen für die kommende Spielzeit an",
        )
        cls = make_cls(industries=["cultural_management"], regions=["stuttgart"])
        score = _actionability_score(art, cls)
        assert score >= 0.35

    def test_teaser_without_hiring_scores_low(self) -> None:
        art = self._art("Concert preview teaser: amazing performance ahead")
        cls = make_cls(industries=["music_classical"])
        score = _actionability_score(art, cls)
        assert score <= 0.4

    def test_local_region_boosts_score(self) -> None:
        # Use a milder signal so the region delta is observable
        art = self._art("Kulturveranstaltung wird verschoben")
        cls_local = make_cls(industries=["cultural_management"], regions=["stuttgart"])
        cls_remote = make_cls(industries=["cultural_management"], regions=["global"])
        assert _actionability_score(art, cls_local) > _actionability_score(art, cls_remote)
