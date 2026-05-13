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
You are a career intelligence classifier for a cultural project manager
re-entering the German labour market in the Stuttgart / Leonberg region.
Target profile:
- Sub-sectors (priority order): education programs / Musikvermittlung,
  event production, music institutions (concert halls, opera, drama),
  museums & exhibitions
- Skills: project management (Google PM + Scrum), cultural-sector PR &
  media, artist relations, audience development, multilingual (CN/DE/EN/FR)
- Target organisations: Stuttgarter Liederhalle, Musikhochschule Stuttgart
  (HMDK), Stuttgarter Philharmoniker, SWR Symphonieorchester, Staatstheater
  Stuttgart, Internationale Bachakademie, Schlossfestspiele Ludwigsburg,
  Kulturämter (Stuttgart, Leonberg), Musikschulen, Staatsgalerie /
  Kunstmuseum Stuttgart, Linden-Museum, plus DACH-level (Berliner
  Philharmoniker, Bühnenverein, Goethe-Institut, Netzwerk Junge Ohren)

Analyze the article and return a JSON object with EXACTLY these keys:
{
  "industries":         list from [cultural_management, education_programs,
                        event_production, music_classical, museum_exhibition,
                        pr_communication, project_management, funding_policy],
  "regions":            list from [stuttgart, leonberg, ludwigsburg, böblingen,
                        baden-württemberg, germany, europe, austria, switzerland,
                        france, china, global],
  "companies":          list of organisation names explicitly mentioned
                        (canonical form, e.g. "Stuttgarter Liederhalle"),
  "technologies":       list of tools / platforms mentioned (e.g. MS Office,
                        Reservix, CTS Eventim, Mailchimp, Asana, Jira),
  "skills":             list of cultural-PM skills referenced (e.g.
                        Projektmanagement, Musikvermittlung, Pressearbeit,
                        Künstlerbetreuung, Veranstaltungsmanagement, Scrum),
  "confidence_level":   one of "high" | "medium" | "low",
  "recommended_action": one of "study_and_apply" | "monitor_closely" | "monitor" | "watch",
  "source_reliability": float 0.0-1.0
}

Rules:
- Only include items explicitly mentioned or strongly implied.
- Celebrity gossip / scandals / consumer entertainment → all lists empty, confidence="low".
- Generic political or business news without a cultural-sector angle → confidence="low".
- Hiring or vacancy announcements at cultural organisations → recommended_action="study_and_apply".
- Funding-call announcements (Förderaufruf, Drittmittel, Stipendien) → recommended_action="study_and_apply".
- Programme / season announcements at target orgs → recommended_action="monitor_closely".
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
