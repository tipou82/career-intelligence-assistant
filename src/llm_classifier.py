"""LLM-based article classifier.

Primary: AnthropicClassifier — uses Claude via the Anthropic API.
Secondary: OpenAIClassifier — kept for reference, not the default.

Quick start:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python -m src.main classify --llm claude

Model default: claude-haiku-4-5 (fast, cheap; ~$0.10 per full 742-article run).
Override with model="claude-sonnet-4-6" for higher accuracy on ambiguous articles.
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
  "industries":         list from [automotive, robotics, adas, functional_safety,
                        embedded, software_defined_vehicle, digital_twin, mbse, ai],
  "regions":            list from [germany, europe, japan, usa, china, korea, global],
  "companies":          list of company names explicitly mentioned (canonical form),
  "technologies":       list of specific technologies (e.g. ROS2, QNX, ISO 26262, SOTIF),
  "skills":             list of relevant skills (e.g. functional safety, fault injection),
  "confidence_level":   one of "high" | "medium" | "low",
  "recommended_action": one of "study_and_apply" | "monitor_closely" | "monitor" | "watch",
  "source_reliability": float 0.0-1.0
}

Rules:
- Only include items explicitly mentioned or strongly implied.
- Generic AI/chatbot news with no embedded or safety angle → industries=["ai"], low confidence.
- Consumer articles (e-bikes, food, politics, sports) → all lists empty, confidence="low".
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

# JSON schema for output_config — guarantees clean JSON, no markdown fences
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "industries":         {"type": "array", "items": {"type": "string"}},
        "regions":            {"type": "array", "items": {"type": "string"}},
        "companies":          {"type": "array", "items": {"type": "string"}},
        "technologies":       {"type": "array", "items": {"type": "string"}},
        "skills":             {"type": "array", "items": {"type": "string"}},
        "confidence_level":   {"type": "string", "enum": ["high", "medium", "low"]},
        "recommended_action": {
            "type": "string",
            "enum": ["study_and_apply", "monitor_closely", "monitor", "watch"],
        },
        "source_reliability": {"type": "number"},
    },
    "required": [
        "industries", "regions", "companies", "technologies", "skills",
        "confidence_level", "recommended_action", "source_reliability",
    ],
    "additionalProperties": False,
}


class AnthropicClassifier:
    """LLM classifier backed by Anthropic Claude (default provider).

    Requires:  pip install anthropic
    Configure: export ANTHROPIC_API_KEY=sk-ant-...

    Cost estimate: claude-haiku-4-5 ≈ $0.001 per 10 articles (~$0.10 for 742 articles).
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5",
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
        """Classify one article. Returns a classification dict."""
        prompt = USER_TEMPLATE.format(title=title, summary=summary[:1500])
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=400,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}
                },
            )
            raw = response.content[0].text if response.content else "{}"
            result = json.loads(raw)
            return {**_DEFAULTS, **result}
        except Exception as exc:
            return {**_DEFAULTS, "_llm_error": str(exc)}


class OpenAIClassifier:
    """LLM classifier backed by OpenAI (secondary option).

    Requires:  pip install openai
    Configure: export OPENAI_API_KEY=sk-...
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        try:
            from openai import OpenAI
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
            return {**_DEFAULTS, **result}
        except Exception as exc:
            return {**_DEFAULTS, "_llm_error": str(exc)}
