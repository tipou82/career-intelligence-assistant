"""Relevance scoring — weighted multi-factor score (1–10) against career profile."""

from typing import Any, Dict, List

# --- Profile targets ---

TARGET_INDUSTRIES: Dict[str, float] = {
    "cultural_management": 1.0,
    "education_programs": 1.0,
    "event_production": 0.95,
    "music_classical": 0.9,
    "project_management": 0.9,
    "pr_communication": 0.8,
    "museum_exhibition": 0.7,
    "funding_policy": 0.65,
}

TARGET_REGIONS: Dict[str, float] = {
    "stuttgart": 1.0,
    "leonberg": 1.0,
    "ludwigsburg": 1.0,
    "böblingen": 1.0,
    "boeblingen": 1.0,
    "sindelfingen": 0.95,
    "baden-württemberg": 0.95,
    "germany": 0.9,
    "deutschland": 0.9,
    "europe": 0.75,
    "europa": 0.75,
    "austria": 0.65,
    "switzerland": 0.65,
    "österreich": 0.65,
    "schweiz": 0.65,
    "france": 0.5,    # Xi has French connection — cooperation roles
    "china": 0.4,     # Goethe-Institut China / cultural-exchange roles
    "global": 0.45,
}

TARGET_SKILLS: Dict[str, float] = {
    # Core cultural-PM skills
    "kulturmanagement": 1.0,
    "cultural management": 1.0,
    "projektmanagement": 1.0,
    "project management": 1.0,
    "projektmanagement kultur": 1.0,
    "projektkoordination": 0.95,
    "projektleitung": 0.95,
    "projektassistenz": 0.85,
    # Education programs
    "musikvermittlung": 1.0,
    "konzertpädagogik": 1.0,
    "musikpädagogik": 0.95,
    "kulturelle bildung": 1.0,
    "music education": 0.95,
    "audience development": 0.9,
    "outreach": 0.85,
    "schulkooperation": 0.85,
    "bildungspartnerschaft": 0.85,
    "kinderkonzert": 0.85,
    "schulkonzert": 0.85,
    "jugendkonzert": 0.8,
    "bildungsreferent": 1.0,
    "education manager": 0.95,
    # Event production
    "veranstaltungsmanagement": 1.0,
    "eventmanagement": 0.95,
    "event management": 0.95,
    "event production": 0.95,
    "konzertdirektion": 0.95,
    "künstlerbetreuung": 0.9,
    "artist relations": 0.85,
    "disposition": 0.85,
    "festival": 0.8,
    "festivalmanagement": 0.9,
    "tour management": 0.8,
    "tournee": 0.8,
    # Music institution domain
    "orchester": 0.85,
    "orchestermanagement": 0.95,
    "konzerthaus": 0.85,
    "philharmonie": 0.85,
    "oper": 0.8,
    "theater": 0.8,
    "klassik": 0.75,
    "klassische musik": 0.8,
    # PR / communication
    "pressearbeit": 0.9,
    "öffentlichkeitsarbeit": 0.9,
    "kommunikation": 0.7,
    "presserefferent": 0.9,
    "pressereferentin": 0.9,
    "media relations": 0.8,
    "social media": 0.65,
    "newsletter": 0.6,
    "redaktion": 0.7,
    "content": 0.55,
    # PM methodology — Xi's in-progress certs
    "scrum": 0.85,
    "scrum master": 0.9,
    "agile": 0.8,
    "google project manager": 0.9,
    "pmp": 0.75,
    "pmi": 0.7,
    "stakeholdermanagement": 0.85,
    "stakeholder management": 0.85,
    # Funding / policy
    "kulturförderung": 0.8,
    "fördermittel": 0.8,
    "drittmittel": 0.8,
    "fundraising": 0.75,
    "sponsoring": 0.7,
    "kulturstiftung": 0.7,
    # Museum domain (sub-sector #4)
    "museumspädagogik": 0.85,
    "ausstellungsmanagement": 0.8,
    "kuratorisch": 0.6,
    "sammlungsmanagement": 0.6,
    # Languages — Xi's trilingual angle
    "mehrsprachig": 0.85,
    "trilingual": 0.85,
    "bilingual": 0.75,
    "interkulturelle kompetenz": 0.85,
    "cross-cultural": 0.8,
    # Productivity tools
    "ms office": 0.45,
    "excel": 0.4,
    "powerpoint": 0.4,
    "ticketing": 0.6,
    "crm": 0.55,
}

# Tier-1 cultural orgs — Xi's primary local targets (Stuttgart region)
TIER_1_COMPANIES = {
    "stuttgarter liederhalle", "liederhalle stuttgart", "liederhalle",
    "musikhochschule stuttgart", "hmdk stuttgart",
    "stuttgarter philharmoniker",
    "swr symphonieorchester", "swr symphonie",
    "staatstheater stuttgart", "staatsoper stuttgart",
    "internationale bachakademie stuttgart", "bachakademie",
    "schlossfestspiele ludwigsburg", "ludwigsburger schlossfestspiele",
    "kulturamt leonberg", "stadt leonberg",
    "kulturamt stuttgart",
    "musikschule stuttgart", "musikschule leonberg",
    "stadthalle leonberg",
}

# Tier-2 cultural orgs — secondary local + DACH-level
TIER_2_COMPANIES = {
    "theaterhaus stuttgart", "theaterhaus",
    "forum am schlosspark", "forum ludwigsburg",
    "stadthalle sindelfingen",
    "junges ensemble stuttgart", "jes",
    "tanzhaus stuttgart",
    "junge oper stuttgart",
    "staatsgalerie stuttgart",
    "kunstmuseum stuttgart",
    "linden-museum", "lindenmuseum",
    "mercedes-benz museum", "porsche museum",
    "stadtmuseum leonberg", "akademie schloss solitude",
    "volkshochschule stuttgart", "vhs stuttgart",
    "kreisvolkshochschule böblingen", "vhs böblingen",
    "berliner philharmoniker", "bayerische staatsoper",
    "elbphilharmonie hamburg", "elbphilharmonie",
    "kölner philharmonie",
    "goethe-institut", "goethe institute",
    "deutsche stiftung musikleben",
    "bundesverband musikunterricht", "bmu",
    "deutscher musikrat",
    "deutscher bühnenverein", "bühnenverein",
    "netzwerk junge ohren", "junge ohren",
    "kulturstiftung des bundes",
    "sks russ", "music & more",
    "cts eventim", "eventim", "reservix",
    "deag", "karsten jahnke",
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
# Prioritises hiring signals, Stuttgart/BW regional fit, and actionability
WEIGHTS_EXTERNAL_TRANSITION = {
    "domain": 0.15,
    "skill": 0.25,
    "company": 0.00,
    "region": 0.15,        # Stuttgart-region fit matters more
    "career_impact": 0.15,
    "source_reliability": 0.10,
    "actionability": 0.20, # hiring + funding-call urgency
}

# Generic hiring vocabulary (cultural-sector terms included)
_HIRING_TERMS = frozenset([
    "hiring", "job opening", "vacancy", "vacancies", "open position",
    "we are hiring", "we're hiring", "join our team", "looking for",
    "job posting", "career opportunity",
    "stellenangebot", "stellenausschreibung", "wir suchen", "stelle frei",
    "ausschreibung", "bewerbung", "stellen frei", "bewerbungsfrist",
    "ab sofort", "zum nächstmöglichen", "festanstellung", "teilzeit", "vollzeit",
    "招聘", "职位", "岗位",  # Chinese hiring terms (Xi reads CN natively)
])

# Restructuring / funding-cut signals — relevant in the public-funded cultural sector
_RESTRUCTURING_TERMS = frozenset([
    "restructuring", "layoffs", "redundancy", "job cuts",
    "downsizing", "restrukturierung", "stellenabbau", "entlassungen",
    "kurzarbeit", "tarifstreit", "haushaltsperre", "etatkürzung",
    "mittelkürzung", "sparmaßnahmen", "schließung", "insolvenz",
    "budget cut", "funding cut",
])

# Cultural-PM job role terms — strong actionability signal
_CULTURAL_JOB_TERMS = frozenset([
    "kulturmanager", "kulturmanagerin", "kulturreferent", "kulturreferentin",
    "projektmanager kultur", "projektmanagerin kultur",
    "projektleiter kultur", "projektleiterin kultur",
    "projektkoordinator kultur", "projektkoordinatorin kultur",
    "projektassistenz kultur",
    "bildungsreferent", "bildungsreferentin",
    "musikvermittler", "musikvermittlerin",
    "veranstaltungsmanager", "veranstaltungsmanagerin",
    "eventmanager", "eventmanagerin",
    "pressereferent", "pressereferentin",
    "kommunikationsreferent", "kommunikationsreferentin",
    "cultural project manager", "education manager",
    "outreach coordinator", "audience development manager",
    "orchestermanager", "konzertdirektion",
    "künstlerische betriebsdirektion",
    "museumspädagoge", "museumspädagogin",
    "ausstellungskoordinator", "ausstellungskoordinatorin",
])

# Cultural-sector "opportunity events" — funding calls, season openings, festival launches
_CULTURAL_OPPORTUNITY_TERMS = frozenset([
    "förderbescheid", "förderaufruf", "ausschreibung", "antragsfrist",
    "saisonstart", "spielzeitbeginn", "festivalauftakt", "premiere",
    "eröffnung", "neue intendanz", "neue leitung", "intendantenwechsel",
    "festakt", "auftakt", "neue spielzeit",
    "kulturförderung", "drittmittel", "stipendium", "residenzprogramm",
])

# Terms that make an article LOW actionability for a cultural-PM
_HYPE_TERMS = frozenset([
    "celebrity", "gossip", "scandal", "viral", "influencer",
    "investment round", "funding round", "unicorn", "ipo", "valuation",
    "billion dollar", "consumer app", "lifestyle",
    "boulevard", "promi", "klatsch", "horoskop",
    "crypto", "cryptocurrency", "nft", "gambling", "casino",
])

_DEMO_WITHOUT_SIGNAL = frozenset([
    "concert preview", "trailer reveal", "teaser",
    "impressive performance", "ovations", "standing ovation",
])

# CJK → English mapping (kept short — Xi reads CN comfortably, scorer just needs canonical tags)
_CJK_TO_EN: Dict[str, str] = {
    "项目管理": "project management",
    "项目经理": "project manager",
    "文化管理": "cultural management",
    "文化项目": "cultural management",
    "音乐教育": "music education",
    "教育项目": "education programs",
    "演出策划": "event production",
    "活动策划": "event production",
    "活动管理": "event management",
    "公关": "pr",
    "公共关系": "public relations",
    "媒体管理": "media relations",
    "媒体公关": "media relations",
    "策展": "curatorial",
    "策展人": "curator",
    "音乐会": "concert",
    "交响乐": "symphony",
    "歌剧": "opera",
    "音乐学院": "conservatoire",
    "博物馆": "museum",
    "展览": "exhibition",
}


def _normalize_cjk_term(term: str) -> str:
    """Map a CJK skill/topic tag to its English equivalent for scoring."""
    return _CJK_TO_EN.get(term, term)


# Source reliability tiers for cultural-sector press
SOURCE_TIERS: Dict[str, float] = {
    # Tier-1 broadsheets / public broadcasters
    "faz": 0.92, "faz feuilleton": 0.92,
    "sz": 0.92, "sz kultur": 0.92, "süddeutsche": 0.92,
    "zeit": 0.92, "zeit kultur": 0.92,
    "deutschlandfunk": 0.92, "deutschlandfunk kultur": 0.92,
    "swr": 0.88, "swr kultur": 0.88,
    "stuttgarter zeitung": 0.85, "stuttgarter zeitung kultur": 0.85,
    "stuttgarter nachrichten": 0.83, "stuttgarter nachrichten kultur": 0.83,
    # Cultural-sector trade press
    "nmz": 0.88, "neue musikzeitung": 0.88,
    "nachtkritik": 0.85, "nachtkritik.de": 0.85,
    "deutscher bühnenverein": 0.85, "bühnenverein": 0.85,
    "backstage pro": 0.78,
    # Cultural management network
    "kulturmanagement network": 0.85, "kulturmanagement.net": 0.85,
    # English classical-music trade
    "the strad": 0.78,
    "gramophone": 0.78,
    "bachtrack": 0.75,
    "slipped disc": 0.62,
    # Company / org press releases (useful but biased)
    "stuttgarter liederhalle": 0.7,
    "musikhochschule stuttgart": 0.7,
    "swr symphonieorchester": 0.72,
    "staatstheater stuttgart": 0.72,
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

    # Pairs that directly map to Xi's target roles
    high_impact_pairs = [
        ("cultural_management", "project management"),
        ("cultural_management", "projektmanagement"),
        ("cultural_management", "kulturmanagement"),
        ("education_programs", "musikvermittlung"),
        ("education_programs", "konzertpädagogik"),
        ("education_programs", "kulturelle bildung"),
        ("education_programs", "bildungsreferent"),
        ("education_programs", "education manager"),
        ("event_production", "veranstaltungsmanagement"),
        ("event_production", "eventmanagement"),
        ("event_production", "konzertdirektion"),
        ("event_production", "künstlerbetreuung"),
        ("music_classical", "musikvermittlung"),
        ("music_classical", "orchestermanagement"),
        ("museum_exhibition", "museumspädagogik"),
        ("museum_exhibition", "bildungsreferent"),
        ("pr_communication", "pressearbeit"),
        ("pr_communication", "öffentlichkeitsarbeit"),
        ("cultural_management", "scrum master"),
        ("cultural_management", "google project manager"),
    ]
    for ind, skill in high_impact_pairs:
        if ind in industries and any(skill in t for t in techs):
            return 1.0

    if industries & {"cultural_management", "education_programs", "event_production"}:
        return 0.8
    if industries & {"music_classical", "pr_communication", "project_management"}:
        return 0.65
    if industries & {"museum_exhibition", "funding_policy"}:
        return 0.5
    return 0.2


def _actionability_score(
    article: Dict[str, Any],
    classification: Dict[str, Any],
) -> float:
    """Score how much this signal should change concrete career actions this week.

    Returns 0.0–1.0. Used only in external_transition mode.

    High (0.7–1.0): job openings, funding calls, season-start hiring, restructuring
    Medium (0.4–0.6): institutional news, sector-policy signals, programme launches
    Low (0.0–0.3): celebrity gossip, viral entertainment, generic hype
    """
    text = (
        (article.get("title") or "") + " " + (article.get("summary") or "")
    ).lower()
    score = 0.25  # baseline

    # Strong positive: explicit hiring or job signal
    if any(t in text for t in _HIRING_TERMS):
        score += 0.45

    # Strong positive: cultural-sector job-role terms
    if any(t in text for t in _CULTURAL_JOB_TERMS):
        score += 0.25

    # Moderate positive: restructuring / funding cuts → opportunity (or warning)
    if any(t in text for t in _RESTRUCTURING_TERMS):
        score += 0.15

    # Moderate positive: cultural opportunity events (Förderaufruf, Saisonstart, etc.)
    if any(t in text for t in _CULTURAL_OPPORTUNITY_TERMS):
        score += 0.15

    # Regional boost: Stuttgart region / BW / Germany signals are most actionable
    regions = {r.lower() for r in classification.get("regions", [])}
    if regions & {"stuttgart", "leonberg", "ludwigsburg", "böblingen", "boeblingen",
                  "baden-württemberg"}:
        score += 0.15
    elif "germany" in regions or "deutschland" in regions:
        score += 0.10
    elif regions & {"europe", "europa", "austria", "switzerland"}:
        score += 0.05

    # Negative: pure hype with no hiring/funding/sector angle
    hype_count = sum(1 for t in _HYPE_TERMS if t in text)
    if hype_count >= 2:
        score *= 0.25
    elif hype_count == 1:
        if not any(t in text for t in _CULTURAL_JOB_TERMS):
            score *= 0.5

    # Negative: previews/teasers with no hiring/programme signal
    if any(t in text for t in _DEMO_WITHOUT_SIGNAL):
        if not any(t in text for t in _HIRING_TERMS | _CULTURAL_JOB_TERMS):
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
        if source_name in SOURCE_TIERS:
            return SOURCE_TIERS[source_name]
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
