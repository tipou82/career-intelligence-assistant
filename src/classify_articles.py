"""Rule-based article classifier with a Protocol interface for future LLM plug-in."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .database import get_unclassified_articles, init_db, update_article_classification
from .score_relevance import score_article

CONFIG_DIR = Path(__file__).parent.parent / "config"


# ---------------------------------------------------------------------------
# LLM classifier interface — implement this Protocol to swap in an LLM later
# ---------------------------------------------------------------------------

class LLMClassifier:
    """Protocol for an LLM-based classifier.

    Implement this class and pass an instance to classify_all() to replace
    the rule-based classifier with an LLM call.

    Expected return dict keys:
        industries, regions, companies, technologies, skills,
        confidence_level, recommended_action, source_reliability
    """

    def classify(self, title: str, summary: str) -> Dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_config() -> Tuple[Dict, Dict, Dict]:
    with open(CONFIG_DIR / "keywords.yaml", encoding="utf-8") as f:
        keywords = yaml.safe_load(f)
    with open(CONFIG_DIR / "companies.yaml", encoding="utf-8") as f:
        companies = yaml.safe_load(f)
    with open(CONFIG_DIR / "sources.yaml", encoding="utf-8") as f:
        sources = yaml.safe_load(f)
    return keywords, companies, sources


# ---------------------------------------------------------------------------
# Rule-based helpers
# ---------------------------------------------------------------------------

_CJK_RANGE = re.compile(
    r"[　-鿿"      # CJK unified, kana, punctuation
    r"豈-﫿"       # CJK compatibility ideographs
    r"︰-﹏"       # CJK compatibility forms
    r"一-鿿"       # CJK unified ideographs (main block)
    r"぀-ヿ"       # Hiragana + Katakana
    r"ㇰ-ㇿ]"      # Katakana phonetic extensions
)


def _is_cjk(text: str) -> bool:
    """Return True if text contains CJK (Chinese / Japanese) characters."""
    return bool(_CJK_RANGE.search(text))


def _term_matches(text: str, terms: List[str]) -> List[str]:
    """Return terms found in text.

    Strategy:
    - CJK terms (Chinese/Japanese): simple substring match — no word boundaries
      exist in CJK scripts, so regex \\b would fail silently.
    - Latin/German terms: word-boundary regex for single words; substring for phrases.
    All matching is case-insensitive for the Latin portion.
    """
    text_lower = text.lower()
    matched = []
    for term in terms:
        term_lower = term.lower()
        if _is_cjk(term):
            # CJK: substring match is correct (no spaces between words)
            if term in text or term_lower in text_lower:
                matched.append(term)
        elif " " in term or any(c in term for c in ("+", "/", ".")):
            # Multi-word Latin/German phrase: simple containment
            if term_lower in text_lower:
                matched.append(term)
        else:
            # Single Latin/German word: word-boundary regex
            pattern = re.escape(term_lower)
            if re.search(r"(?<!\w)" + pattern + r"(?!\w)", text_lower):
                matched.append(term)
    return matched


def _extract_industries(text: str, domain_map: Dict[str, List[str]]) -> List[str]:
    """Detect industry domains via domain marker words.

    Uses simple substring matching for all languages — this already handles CJK
    correctly since Chinese/Japanese markers are CJK strings that appear verbatim
    in the text without surrounding spaces.
    """
    detected = []
    text_lower = text.lower()
    for industry, markers in domain_map.items():
        for m in markers:
            # CJK markers: match verbatim; Latin markers: case-insensitive lower
            if _is_cjk(m):
                if m in text:
                    detected.append(industry)
                    break
            elif m.lower() in text_lower:
                detected.append(industry)
                break
    return detected


def _get_source_reliability(source_name: str, sources_config: Dict) -> float:
    for feed in sources_config.get("feeds", []):
        if feed.get("name") == source_name:
            return float(feed.get("reliability", 0.5))
    return 0.5


def _confidence_from_reliability(reliability: float) -> str:
    if reliability >= 0.8:
        return "high"
    if reliability >= 0.5:
        return "medium"
    return "low"


def _is_noise(text: str, noise_terms: List[str]) -> bool:
    text_lower = text.lower()
    return sum(1 for t in noise_terms if t.lower() in text_lower) >= 2


def _recommended_action(
    industries: List[str],
    technologies: List[str],
    skills: List[str],
    companies: List[str],
) -> str:
    high_value = {"ros2", "qnx", "iso/pas 8800", "sotif", "sysml", "mbse",
                  "fault injection", "embedded ai", "ai perception"}
    combined_lower = {t.lower() for t in technologies + skills}
    if combined_lower & high_value:
        return "study_and_apply"
    if any(ind in industries for ind in ("robotics", "adas", "functional_safety")):
        return "monitor_closely"
    if companies:
        return "monitor"
    return "watch"


# ---------------------------------------------------------------------------
# Rule-based classifier
# ---------------------------------------------------------------------------

def rule_based_classify(
    title: str,
    summary: str,
    keywords: Dict,
    companies_cfg: Dict,
    source_name: str,
    sources_config: Dict,
) -> Dict[str, Any]:
    """Classify a single article using keyword and entity matching."""
    combined = f"{title} {summary}"

    # Industries
    domain_map = keywords.get("industries", {}).get("domain_map", {})
    industries = _extract_industries(combined, domain_map)
    base_terms = keywords.get("industries", {}).get("terms", [])
    for t in _term_matches(combined, base_terms):
        normalized = t.lower().replace(" ", "_").replace("-", "_")
        if normalized not in industries:
            industries.append(normalized)

    # Regions
    regions = _term_matches(combined, keywords.get("regions", {}).get("terms", []))

    # Companies (check name + aliases)
    matched_companies: List[str] = []
    combined_lower = combined.lower()
    for _sector, company_list in companies_cfg.get("companies", {}).items():
        for company in company_list:
            if not isinstance(company, dict):
                continue
            candidates = [company.get("name", "")] + company.get("aliases", [])
            if any(c.lower() in combined_lower for c in candidates if c):
                matched_companies.append(company["name"])

    # Technologies and skills
    technologies = _term_matches(combined, keywords.get("technologies", {}).get("terms", []))
    skills = _term_matches(combined, keywords.get("skills", {}).get("terms", []))

    # Source reliability
    reliability = _get_source_reliability(source_name, sources_config)
    confidence_level = _confidence_from_reliability(reliability)

    # Noise check — downgrade confidence if article looks off-topic
    noise_terms = keywords.get("noise_indicators", [])
    if _is_noise(combined, noise_terms) and not industries:
        confidence_level = "low"

    action = _recommended_action(industries, technologies, skills, matched_companies)

    return {
        "industries": sorted(set(industries)),
        "regions": sorted(set(regions)),
        "companies": sorted(set(matched_companies)),
        "technologies": sorted(set(technologies)),
        "skills": sorted(set(skills)),
        "confidence_level": confidence_level,
        "recommended_action": action,
        "source_reliability": reliability,
    }


# ---------------------------------------------------------------------------
# Signal strength
# ---------------------------------------------------------------------------

def _signal_strength(score: float) -> str:
    if score >= 6.5:
        return "strong"
    if score >= 3.5:
        return "weak"
    return "noise"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_all(
    llm_classifier: Optional[LLMClassifier] = None,
) -> Dict[str, int]:
    """Classify all articles that have not yet been classified.

    Pass an LLMClassifier instance to use LLM-based classification instead of
    the built-in rule-based approach.

    Returns a stats dict with keys: classified, skipped.
    """
    init_db()
    keywords, companies_cfg, sources_config = _load_config()
    articles = get_unclassified_articles()
    stats: Dict[str, int] = {"classified": 0, "skipped": 0}

    for article in articles:
        title = article.get("title", "")
        summary = article.get("summary", "")

        if llm_classifier is not None:
            classification = llm_classifier.classify(title, summary)
        else:
            classification = rule_based_classify(
                title,
                summary,
                keywords,
                companies_cfg,
                article.get("source_name", ""),
                sources_config,
            )

        scores = score_article(article, classification, keywords, companies_cfg, sources_config)
        strength = _signal_strength(scores["total"])

        update_article_classification(
            article_id=article["id"],
            classification=classification,
            relevance_score=scores["total"],
            confidence_level=classification.get("confidence_level", "low"),
            signal_strength=strength,
            recommended_action=classification.get("recommended_action", "watch"),
        )
        stats["classified"] += 1

    return stats
