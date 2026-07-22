"""LLM call #1 — constrained intent routing. Picks a template_id + fills slots.

The model classifies into a closed set of templates and returns JSON only. It never
writes SQL and never resolves relative dates (it echoes phrases like "last six months"
verbatim; Python resolves them). template_id=null is a valid, expected answer.
"""
from __future__ import annotations

import json

from app.config import DEMO_NOW
from app.templates.registry import REGISTRY
from app.llm.client import complete


def _system_prompt() -> str:
    lines = [
        "You route a natural-language question about a police crime database to ONE of the",
        "query templates below, or to null if none fit.",
        f"\nToday's date is {DEMO_NOW.isoformat()}.",
        "\nTemplates:",
    ]
    for t in REGISTRY.values():
        lines.append(
            f"- {t.template_id}: {t.description}\n"
            f"    required slots: {', '.join(t.required_slots)}\n"
            f"    optional slots: {', '.join(t.optional_slots) or '(none)'}")
    lines += [
        "\nSlot-filling rules:",
        "- Return relative time expressions VERBATIM (e.g. \"last six months\", \"this quarter\").",
        "  Do NOT compute dates. Use slot key 'period' for a single range;",
        "  'period_a' and 'period_b' for period-over-period comparison templates.",
        "- crime_type, status, station, division, district, fir_number: copy the user's words.",
        "- Only include slots you actually have evidence for. Omit the rest.",
        "\nRespond with JSON ONLY — no prose, no markdown fences. Schema:",
        '{"template_id": "<id or null>", "slots": {..}, "confidence": "high|medium|low"}',
        'If nothing fits, respond: {"template_id": null, "reason": "<why>"}',
        "Refusing (template_id=null) is a valid, expected answer, not a failure.",
    ]
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    text = text[text.find("{"): text.rfind("}") + 1]
    return json.loads(text)


def route(question: str) -> dict:
    """Return {'template_id': str|None, 'slots': {...}, 'confidence': str, 'reason'?: str}."""
    system = _system_prompt()
    for terse in (False, True):
        try:
            out = _parse(complete(system, question, max_tokens=400))
            if "template_id" not in out:
                raise ValueError("no template_id")
            tid = out["template_id"]
            if tid is not None and tid not in REGISTRY:
                raise ValueError(f"unknown template_id {tid}")
            out.setdefault("slots", {})
            out.setdefault("confidence", "low")
            return out
        except (json.JSONDecodeError, ValueError):
            if terse:
                return {"template_id": None, "reason": "Could not interpret the question."}
            system += "\n\nIMPORTANT: your previous reply was not valid JSON. Return JSON only."
    return {"template_id": None, "reason": "Could not interpret the question."}
