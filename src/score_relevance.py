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
    "japan": 0.9,
    "usa": 0.8,
    "china": 0.8,   # major market: BYD, NIO, XPeng, Huawei, Baidu — strong signal value
    "korea": 0.65,
    "global": 0.6,
    "north america": 0.75,
    "asia": 0.6,
    # "europe" removed — too broad; Germany already captures the relevant signal
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

# Weights — default mode
WEIGHTS = {
    "domain": 0.22,
    "skill": 0.30,
    "company": 0.00,
    "region": 0.10,
    "career_impact": 0.25,
    "source_reliability": 0.13,
}

# Weights — external_transition mode
# Prioritises employability signals, Germany/Europe fit, and actionability
# over general trend coverage.
WEIGHTS_EXTERNAL_TRANSITION = {
    "domain": 0.15,
    "skill": 0.25,
    "company": 0.00,
    "region": 0.15,        # Germany/Europe fit matters more
    "career_impact": 0.15,
    "source_reliability": 0.10,
    "actionability": 0.20, # new dimension
}

# Terms that strongly signal career actionability for a senior safety architect
_HIRING_TERMS = frozenset([
    "hiring", "job opening", "vacancy", "vacancies", "open position",
    "we are hiring", "we're hiring", "join our team", "looking for",
    "job posting", "career opportunity", "stellenangebot", "wir suchen",
    "stelle", "stellenausschreibung", "bewerbung", "stellen frei",
    "求人", "採用", "募集",  # Japanese hiring terms
    "招聘", "职位", "岗位",  # Chinese hiring terms
])
_RESTRUCTURING_TERMS = frozenset([
    "restructuring", "layoffs", "redundancy", "job cuts", "headcount reduction",
    "downsizing", "restrukturierung", "stellenabbau", "entlassungen",
    "kurzarbeit", "workforce reduction",
])
_SAFETY_JOB_TERMS = frozenset([
    "safety engineer", "safety architect", "functional safety", "system safety",
    "safety manager", "safety consultant", "safety assessor", "safety case",
    "iso 26262", "iso 13849", "iec 61508", "iec 62061", "sotif", "iso/pas 8800",
    "cmse", "tüv", "tuv", "fsae", "fse certified",
    "safety-critical", "rams engineer", "safety certification",
])
_STANDARD_EVENT_TERMS = frozenset([
    "iso 13849", "iec 61508", "iec 62061", "iso 26262", "sotif", "iso/pas 8800",
    "cmse certification", "tüv certification", "safety standard", "safety regulation",
    "machinery directive", "eu ai act", "new standard", "standard update",
])
# Terms that make an article LOW actionability for a safety architect
_HYPE_TERMS = frozenset([
    "chatgpt", "chatbot", "viral", "social media", "influencer", "celebrity",
    "investment round", "funding round", "unicorn", "ipo", "valuation",
    "billion dollar", "marketing", "brand", "consumer app", "lifestyle",
    "entertainment", "sports", "gaming",
])
_DEMO_WITHOUT_SIGNAL = frozenset([
    "humanoid demo", "robot dance", "concept car", "prototype reveal",
    "impressive demo", "viral robot", "amazing robot",
])

_CJK_TO_EN: Dict[str, str] = {
    # Functional safety
    "功能安全": "functional safety",
    "機能安全": "functional safety",
    "安全完整性": "safety integrity",
    "失效安全": "fail-safe",
    "安全规格": "safety integrity",
    "安全規格": "safety integrity",
    # Standards
    "预期功能安全": "sotif",
    "預期機能安全": "sotif",
    # AI perception / monitoring
    "嵌入式AI": "embedded ai",
    "組み込みAI": "embedded ai",
    "感知算法": "ai perception",
    "传感器融合": "sensor fusion",
    "センサーフュージョン": "sensor fusion",
    "置信度监控": "confidence monitoring",
    "遅延監視": "latency monitoring",
    # Fault injection
    "故障注入": "fault injection",
    # Robots / physical
    "人形机器人": "humanoid",
    "人型ロボット": "humanoid",
    "ヒューマノイド": "humanoid",
    "物理AI": "physical ai",
    "具身智能": "physical ai",
    # Reinforcement / ML
    "强化学习": "reinforcement learning",
    "強化学習": "reinforcement learning",
    "深度学习": "deep learning",
    "深層学習": "deep learning",
    "机器学习": "machine learning",
    "機械学習": "machine learning",
    "神经网络": "neural network",
    "ニューラルネットワーク": "neural network",
    # Digital twin / simulation
    "数字孪生": "digital twin",
    "デジタルツイン": "digital twin",
    "虚拟验证": "virtual validation",
    "バーチャル検証": "virtual validation",
    "仿真": "simulation",
    "シミュレーション": "simulation",
    # ADAS / autonomous
    "自动驾驶": "autonomous driving",
    "自動運転": "autonomous driving",
    "自律走行": "autonomous driving",
    # Embedded / OS
    "实时操作系统": "rtos",
    "リアルタイムOS": "rtos",
    "激光雷达": "lidar",
    "レーザーレーダー": "lidar",
    # MBSE / SysML
    "基于模型": "mbse",
    "モデルベース": "model-based",
    # Safety mechanisms
    "安全机制": "safety mechanism",
    "安全メカニズム": "safety mechanism",
    "监控": "perception monitoring",
    "監視": "perception monitoring",
    # Requirements
    "需求追溯": "requirements traceability",
    "要求トレーサビリティ": "requirements traceability",
}


def _normalize_cjk_term(term: str) -> str:
    """Map a CJK technology/skill tag to its English equivalent for scoring.

    Returns the original term if no mapping exists.
    """
    return _CJK_TO_EN.get(term, term)


# Source tiers for reliability scoring — used when source_name is available on the article.
# Scores are blended with the feed-level reliability from sources.yaml.
SOURCE_TIERS: Dict[str, float] = {
    # Academic / standards bodies (most trusted)
    "ieee": 0.97,
    "sae": 0.97,
    "iso": 0.97,
    "iec": 0.95,
    "nist": 0.95,
    "acm": 0.95,
    "robohub": 0.90,           # academic robotics
    "mit technology review": 0.88,
    # Major international news agencies and publishers
    "reuters": 0.92,
    "nikkei": 0.90,
    "nikkei asia": 0.90,
    "handelsblatt": 0.87,
    "automotive news": 0.85,
    "ee times": 0.83,
    "ee times europe": 0.83,
    "ee journal": 0.80,
    "embedded.com": 0.82,
    "automotive world": 0.78,
    "heise online": 0.78,
    "heise auto": 0.78,
    "heise developer": 0.78,
    "wired": 0.72,
    "golem.de": 0.68,
    # Tech blogs / enthusiast press (lower trust)
    "techcrunch": 0.62,
    "venturebeat": 0.60,
    "technode": 0.62,
    "electrek": 0.58,
    "the drive": 0.55,
    # Company newsrooms / press releases (useful but potentially biased)
    "nvidia blog": 0.72,
    "nvidia developer blog": 0.70,
    "arm newsroom": 0.72,
    "zf press": 0.72,
}


# --- Component scorers ---

def _domain_score(classification: Dict[str, Any]) -> float:
    industries = [i.lower() for i in classification.get("industries", [])]
    if not industries:
        return 0.0
    return max(TARGET_INDUSTRIES.get(ind, 0.05) for ind in industries)


def _skill_score(classification: Dict[str, Any]) -> float:
    raw = classification.get("technologies", []) + classification.get("skills", [])
    if not raw:
        return 0.0
    # Normalize CJK tags to English equivalents before lookup
    combined = [_normalize_cjk_term(t).lower() for t in raw]
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
    # Normalize CJK technology tags before matching against high-impact pairs
    techs = {
        _normalize_cjk_term(t).lower()
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


def _actionability_score(
    article: Dict[str, Any],
    classification: Dict[str, Any],
) -> float:
    """Score how much this signal should change concrete career actions this week.

    Returns 0.0–1.0. Used only in external_transition mode.

    High (0.7–1.0): job openings, hiring signals, restructuring, safety standards events
    Medium (0.4–0.6): company safety news, regulations, technology signals
    Low (0.0–0.3): generic GenAI, consumer hype, demos without hiring/safety signal
    """
    text = (
        (article.get("title") or "") + " " + (article.get("summary") or "")
    ).lower()
    score = 0.25  # baseline

    # Strong positive: explicit hiring or job signal
    if any(t in text for t in _HIRING_TERMS):
        score += 0.45

    # Strong positive: safety-specific job role terms
    if any(t in text for t in _SAFETY_JOB_TERMS):
        score += 0.25

    # Moderate positive: restructuring → opportunity elsewhere
    if any(t in text for t in _RESTRUCTURING_TERMS):
        score += 0.15

    # Moderate positive: safety standards events → certification/consulting demand
    if any(t in text for t in _STANDARD_EVENT_TERMS):
        score += 0.15

    # Regional boost: Germany/Europe signals are most actionable
    regions = {r.lower() for r in classification.get("regions", [])}
    if "germany" in regions:
        score += 0.10
    elif "europe" in regions:
        score += 0.05

    # Negative: pure hype with no safety/hiring angle
    hype_count = sum(1 for t in _HYPE_TERMS if t in text)
    if hype_count >= 2:
        score *= 0.25
    elif hype_count == 1:
        # Only penalise if no safety terms present
        if not any(t in text for t in _SAFETY_JOB_TERMS):
            score *= 0.5

    # Negative: demos with no hiring/production/safety signal
    if any(t in text for t in _DEMO_WITHOUT_SIGNAL):
        if not any(t in text for t in _HIRING_TERMS | _SAFETY_JOB_TERMS):
            score *= 0.3

    return min(score, 1.0)


def _source_reliability_score(
    classification: Dict[str, Any],
    article: Dict[str, Any] | None = None,
) -> float:
    """Return source reliability score.

    Blends:
    1. Feed-level reliability from sources.yaml (stored in classification dict).
    2. Named-source tier from SOURCE_TIERS (keyed on article source_name, lowercase).

    If a source_name matches a known tier, that value takes precedence.
    Falls back to the feed-level value, then to 0.5 for unknown sources.
    """
    feed_score = min(float(classification.get("source_reliability", 0.5)), 1.0)

    if article:
        source_name = str(article.get("source_name", "")).lower().strip()
        # Exact match first
        if source_name in SOURCE_TIERS:
            return SOURCE_TIERS[source_name]
        # Partial match — e.g. "IEEE Spectrum Robotics" → "ieee"
        for key, val in SOURCE_TIERS.items():
            if key in source_name or source_name.startswith(key):
                return val

    return feed_score


# --- Public API ---

def score_article(
    article: Dict[str, Any],
    classification: Dict[str, Any],
    keywords: Dict,
    companies: Dict,
    sources_config: Dict,
    career_mode: str = "default",
) -> Dict[str, float]:
    """Compute weighted relevance score and career actionability score.

    Returns a dict with component scores (0–10 scale), 'total', and
    'actionability' (0–10, always computed regardless of mode).
    """
    domain = _domain_score(classification)
    skill = _skill_score(classification)
    region = _region_score(classification)
    career_impact = _career_impact_score(classification)
    source_rel = _source_reliability_score(classification, article)
    actionability = _actionability_score(article, classification)

    if career_mode == "external_transition":
        w = WEIGHTS_EXTERNAL_TRANSITION
        total = (
            domain * w["domain"]
            + skill * w["skill"]
            + region * w["region"]
            + career_impact * w["career_impact"]
            + source_rel * w["source_reliability"]
            + actionability * w["actionability"]
        ) * 10.0
    else:
        w = WEIGHTS
        total = (
            domain * w["domain"]
            + skill * w["skill"]
            + region * w["region"]
            + career_impact * w["career_impact"]
            + source_rel * w["source_reliability"]
        ) * 10.0

    return {
        "domain": round(domain * 10, 2),
        "skill": round(skill * 10, 2),
        "region": round(region * 10, 2),
        "career_impact": round(career_impact * 10, 2),
        "source_reliability": round(source_rel * 10, 2),
        "actionability": round(actionability * 10, 2),
        "total": round(min(total, 10.0), 2),
    }
