"""Relevance scoring — weighted multi-factor score (1–10) against career profile."""

from typing import Any, Dict, List

# --- Profile targets ---

TARGET_INDUSTRIES: Dict[str, float] = {
    "automotive": 1.0,
    "robotics": 1.0,
    "adas": 1.0,
    "functional_safety": 1.0,
    "embedded": 0.9,
    "software_defined_vehicle": 0.9,
    "digital_twin": 0.85,
    "mbse": 0.85,
    "ai": 0.8,
    "physical_ai": 0.9,
    "machinery_safety": 0.9,
}

TARGET_REGIONS: Dict[str, float] = {
    "germany": 1.0,
    "europe": 0.9,
    "japan": 0.9,
    "usa": 0.8,
    "china": 0.7,
    "korea": 0.6,
    "global": 0.6,
    "north america": 0.7,
    "asia": 0.5,
}

TARGET_SKILLS: Dict[str, float] = {
    # Core safety standards
    "ros2": 1.0,
    "c++20": 1.0,
    "functional safety": 1.0,
    "iso 26262": 1.0,
    "sotif": 1.0,
    "iso/pas 8800": 1.0,
    # AI perception and monitoring (strongest differentiator)
    "ai perception monitoring": 1.0,
    "confidence monitoring": 1.0,
    "latency monitoring": 0.95,
    "stale data": 0.95,
    "fault injection": 0.95,
    "safety testing": 0.95,
    "embedded ai": 0.95,
    "ai perception": 0.9,
    "perception monitoring": 0.9,
    "ai safety validation": 0.95,
    "ai reliability": 0.9,
    "plausibility check": 0.9,
    "degraded mode": 0.9,
    "safe state": 0.9,
    # Machinery safety (ISO 13849 / CMSE)
    "iso 13849": 1.0,
    "performance level": 0.95,
    "pl d": 0.95,
    "pl e": 0.95,
    "plr": 0.9,
    "safety function": 0.95,
    "srp/cs": 0.9,
    "mttfd": 0.9,
    "dcavg": 0.9,
    "ccf": 0.85,
    "categoria": 0.8,
    "iec 62061": 0.85,
    "cmse": 0.9,
    "machinery directive": 0.8,
    "emergency stop": 0.85,
    "protective stop": 0.85,
    "safe speed": 0.85,
    "collaborative robot": 0.9,
    "iso 10218": 0.85,
    "iso/ts 15066": 0.85,
    # Safety standards and mechanisms
    "safety mechanism": 0.9,
    "safety concept": 0.9,
    "asil": 0.85,
    "hara": 0.8,
    "fmea": 0.8,
    "fta": 0.8,
    "safety case": 0.8,
    "assurance case": 0.8,
    # Architecture and systems
    "mbse": 0.85,
    "sysml": 0.85,
    "digital twin": 0.85,
    "virtual validation": 0.85,
    "virtual twin": 0.85,
    "physical ai": 0.85,
    "humanoid": 0.85,
    "system architecture": 0.8,
    "requirements engineering": 0.8,
    "requirements traceability": 0.85,
    "traceability": 0.75,
    # Embedded / OS
    "qnx": 0.9,
    "embedded linux": 0.8,
    "rtos": 0.8,
    "posix": 0.75,
    "watchdog": 0.8,
    "supervisor": 0.75,
    "autosar": 0.75,
    # General
    "python": 0.6,
    "technical documentation": 0.7,
}

TIER_1_COMPANIES = {
    "bosch", "robert bosch", "continental", "zf", "mercedes-benz", "mercedes",
    "bmw", "volkswagen", "vw", "toyota", "tesla", "nvidia", "qualcomm",
    "mobileye", "arm", "neura robotics", "figure ai", "boston dynamics",
    "dassault", "dassault systèmes", "dassault systemes",
    "pilz", "sick", "schmersal", "kuka", "fanuc", "yaskawa",
    "denso", "honda", "panasonic",
}

TIER_2_COMPANIES = {
    "honda", "hyundai", "porsche", "byd", "geely", "nio", "xpeng",
    "agility robotics", "unitree", "ubtech", "abb", "kuka", "fanuc",
    "yaskawa", "kawasaki", "openai", "google deepmind", "deepmind",
    "anthropic", "microsoft", "huawei", "baidu", "amd", "intel",
}

# Weights (must sum to 1.0)
WEIGHTS = {
    "domain": 0.20,
    "skill": 0.25,
    "company": 0.15,
    "region": 0.10,
    "career_impact": 0.20,
    "source_reliability": 0.10,
}


# --- Component scorers ---

def _domain_score(classification: Dict[str, Any]) -> float:
    industries = [i.lower() for i in classification.get("industries", [])]
    if not industries:
        return 0.0
    return max(TARGET_INDUSTRIES.get(ind, 0.05) for ind in industries)


def _skill_score(classification: Dict[str, Any]) -> float:
    combined = [
        t.lower()
        for t in classification.get("technologies", []) + classification.get("skills", [])
    ]
    if not combined:
        return 0.0
    return max(TARGET_SKILLS.get(item, 0.05) for item in combined)


def _company_score(classification: Dict[str, Any]) -> float:
    companies = {c.lower() for c in classification.get("companies", [])}
    if not companies:
        return 0.0
    if companies & TIER_1_COMPANIES:
        return 1.0
    if companies & TIER_2_COMPANIES:
        return 0.6
    return 0.15


def _region_score(classification: Dict[str, Any]) -> float:
    regions = [r.lower() for r in classification.get("regions", [])]
    if not regions:
        return 0.3  # unknown region — partial credit
    return max(TARGET_REGIONS.get(r, 0.15) for r in regions)


def _career_impact_score(classification: Dict[str, Any]) -> float:
    """Estimate career impact from the combination of domain and skills."""
    industries = {i.lower() for i in classification.get("industries", [])}
    techs = {
        t.lower()
        for t in classification.get("technologies", []) + classification.get("skills", [])
    }

    # Pairs that directly map to the user's target role
    high_impact_pairs = [
        ("robotics", "ros2"),
        ("robotics", "functional safety"),
        ("robotics", "iso 13849"),
        ("robotics", "safety function"),
        ("robotics", "performance level"),
        ("adas", "sotif"),
        ("adas", "iso/pas 8800"),
        ("adas", "ai perception"),
        ("automotive", "functional safety"),
        ("automotive", "mbse"),
        ("embedded", "qnx"),
        ("ai", "safety"),
        ("ai", "fault injection"),
        ("ai", "confidence monitoring"),
        ("functional_safety", "iso/pas 8800"),
        ("functional_safety", "iso 13849"),
        ("software_defined_vehicle", "functional safety"),
    ]
    for ind, skill in high_impact_pairs:
        if ind in industries and any(skill in t for t in techs):
            return 1.0

    if industries & {"robotics", "adas", "functional_safety"}:
        return 0.8
    if industries & {"automotive", "embedded", "software_defined_vehicle"}:
        return 0.65
    if industries & {"ai", "mbse", "digital_twin"}:
        return 0.5
    return 0.2


def _source_reliability_score(classification: Dict[str, Any]) -> float:
    return min(float(classification.get("source_reliability", 0.5)), 1.0)


# --- Public API ---

def score_article(
    article: Dict[str, Any],
    classification: Dict[str, Any],
    keywords: Dict,  # reserved for future use
    companies: Dict,  # reserved for future use
    sources_config: Dict,  # reserved for future use
) -> Dict[str, float]:
    """Compute weighted relevance score.

    Returns a dict with individual component scores (0–10 scale) and 'total'.
    """
    domain = _domain_score(classification)
    skill = _skill_score(classification)
    company = _company_score(classification)
    region = _region_score(classification)
    career_impact = _career_impact_score(classification)
    source_rel = _source_reliability_score(classification)

    total = (
        domain * WEIGHTS["domain"]
        + skill * WEIGHTS["skill"]
        + company * WEIGHTS["company"]
        + region * WEIGHTS["region"]
        + career_impact * WEIGHTS["career_impact"]
        + source_rel * WEIGHTS["source_reliability"]
    ) * 10.0

    return {
        "domain": round(domain * 10, 2),
        "skill": round(skill * 10, 2),
        "company": round(company * 10, 2),
        "region": round(region * 10, 2),
        "career_impact": round(career_impact * 10, 2),
        "source_reliability": round(source_rel * 10, 2),
        "total": round(min(total, 10.0), 2),
    }
