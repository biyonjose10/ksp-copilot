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
        "query templates below. Pick the single best-fitting template.",
        f"\nToday's date is {DEMO_NOW.isoformat()}.",
        "\nTemplates:",
    ]
    for t in REGISTRY.values():
        lines.append(f"- {t.template_id}: {t.description}\n"
                     f"    slots it can use: {', '.join(t.required_slots + t.optional_slots)}")
    lines += [
        "\nHow to choose:",
        "- 'show / list / which cases' about a crime type or place -> T1.",
        "- 'how many ... open / closed / pending' -> T2.",
        "- 'biggest increase / decrease ... vs / compared to ...' -> T3.",
        "- a specific FIR number -> T4.",
        "- 'caseload / how many cases at <station>' -> T5.",
        "- 'most common / top crimes' -> T6.",
        "\nSlot-filling rules:",
        "- Fill only the slots you can see in the question; omit the rest.",
        "- Copy crime_type, status, station, division, district, fir_number from the user's words.",
        "- Time periods: copy relative phrases VERBATIM (\"last six months\", \"this quarter\").",
        "  Do NOT compute dates. Use 'period' for one range; 'period_a' and 'period_b' for",
        "  comparisons. Expand ellipsis: \"this quarter compared to last\" ->",
        "  period_a=\"this quarter\", period_b=\"last quarter\".",
        "\nIMPORTANT — when to return null:",
        "- A MISSING time period, area, or count is NEVER a reason to return null. The backend",
        "  fills those in (missing dates default to all records). Just pick the template and",
        "  leave the slot out. Do NOT refuse because a date range or place is absent.",
        "- Return null ONLY when the question is not about crime records at all — e.g. weather,",
        "  food, opinions, or predictions about a person ('is he likely to solve it?').",
        "\nRespond with JSON ONLY — no prose, no markdown fences. Schema:",
        '{"template_id": "<id or null>", "slots": {..}, "confidence": "high|medium|low"}',
        'When the question is out of scope: {"template_id": null, "reason": "<short why>"}',
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
