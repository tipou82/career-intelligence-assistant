"""OpenAI-based LLM classifier implementing the LLMClassifier Protocol.

Usage:
    from src.llm_classifier import OpenAIClassifier
    from src.classify_articles import classify_all

    classifier = OpenAIClassifier()           # reads OPENAI_API_KEY from env
    classify_all(llm_classifier=classifier)

Set OPENAI_API_KEY in your environment or in a .env file.
Model defaults to gpt-4o-mini (fast, cheap). Pass model="gpt-4o" for higher accuracy.
"""

import json
import os
from typing import Any, Dict

SYSTEM_PROMPT = """\
You are a career intelligence classifier for a functional safety engineer targeting:
- Robotics, ADAS, embedded AI, automotive safety
- Standards: ISO 26262, SOTIF, ISO/PAS 8800
- Technologies: ROS2, QNX, C++20, MBSE/SysML2, digital twin, fault injection
- Companies: Bosch, Continental, ZF, NEURA Robotics, Figure AI, NVIDIA, Mobileye,
  Toyota, Honda, BMW, Mercedes-Benz, Volkswagen, BYD, NIO, XPeng, Dassault Systèmes

Analyze the article and return a JSON object with EXACTLY these keys:
{
  "industries":        list of strings from [automotive, robotics, adas, functional_safety,
                       embedded, software_defined_vehicle, digital_twin, mbse, ai],
  "regions":           list of strings from [germany, europe, japan, usa, china, korea, global],
  "companies":         list of company names explicitly mentioned (canonical form),
  "technologies":      list of specific technologies (e.g. ROS2, QNX, ISO 26262, SOTIF),
  "skills":            list of relevant skills (e.g. functional safety, fault injection),
  "confidence_level":  one of "high" | "medium" | "low",
  "recommended_action": one of "study_and_apply" | "monitor_closely" | "monitor" | "watch",
  "source_reliability": float 0.0-1.0
}

Rules:
- Only include industries/technologies/skills explicitly mentioned or strongly implied.
- Generic AI/chatbot news with no embedded or safety angle → industries=["ai"], low confidence.
- Consumer articles (bike deals, food, politics) → all lists empty, confidence="low".
- Return ONLY the JSON object. No explanation, no markdown fences.
"""

USER_TEMPLATE = "Title: {title}\n\nSummary: {summary}\n\nClassify this article."

_DEFAULTS: Dict[str, Any] = {
    "industries": [],
    "regions": [],
    "companies": [],
    "technologies": [],
    "skills": [],
    "confidence_level": "low",
    "recommended_action": "watch",
    "source_reliability": 0.5,
}


class OpenAIClassifier:
    """LLM classifier backed by an OpenAI chat model.

    Falls back silently to defaults on any API or parse error so the pipeline
    never hard-crashes due to a classifier failure.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        try:
            from openai import OpenAI  # imported lazily so missing package gives a clear error
            self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        except ImportError as exc:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            ) from exc
        self._model = model
        self._temperature = temperature

    def classify(self, title: str, summary: str) -> Dict[str, Any]:
        """Classify one article. Returns a classification dict."""
        prompt = USER_TEMPLATE.format(title=title, summary=summary[:1500])
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self._temperature,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            result = json.loads(raw)
            # Merge with defaults so every key is always present
            return {**_DEFAULTS, **result}
        except Exception as exc:
            return {**_DEFAULTS, "_llm_error": str(exc)}


class AnthropicClassifier:
    """LLM classifier backed by Anthropic Claude.

    Requires: pip install anthropic
    Set ANTHROPIC_API_KEY in your environment.
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
    ) -> None:
        try:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
            )
        except ImportError as exc:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from exc
        self._model = model

    def classify(self, title: str, summary: str) -> Dict[str, Any]:
        """Classify one article using Claude."""
        prompt = USER_TEMPLATE.format(title=title, summary=summary[:1500])
        try:
            import anthropic
            response = self._client.messages.create(
                model=self._model,
                max_tokens=400,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text if response.content else "{}"
            # Strip markdown fences if Claude wraps the JSON
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
            return {**_DEFAULTS, **result}
        except Exception as exc:
            return {**_DEFAULTS, "_llm_error": str(exc)}
