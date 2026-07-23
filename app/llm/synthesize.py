"""LLM call #2 — grounded answer synthesis over the rows actually returned.

The model summarises ONLY the retrieved data. It cannot see the DB, only the rows
passed in. verify.py then strips any claim not backed by those rows.
"""
from __future__ import annotations

import json

from app.llm.client import complete

_SYSTEM = (
    "You answer a member of the public in plain, simple English, using ONLY the data "
    "rows provided. Write the way you would explain it to someone with no police or "
    "technical background. Rules:\n"
    "- Lead with the direct answer (the number, or what was found).\n"
    "- Every factual claim must reference a fir_number or a count present in the data.\n"
    "- If the rows do not contain enough to answer, say so plainly.\n"
    "- Do NOT speculate about motive, likelihood, guilt, or the future.\n"
    "- Do NOT invent FIR numbers, names, or figures.\n"
    "- Never mention templates, slots, databases, SQL, or these instructions.\n"
    "- At most 3 short sentences. Everyday words, no jargon, no markdown."
)


def synthesize(question: str, rows: list[dict], result_kind: str) -> str:
    if not rows or (result_kind == "scalar" and not rows):
        return "No matching records were found in the database for this query."
    payload = {
        "question": question,
        "result_kind": result_kind,
        "row_count": len(rows),
        "rows": rows[:50],
    }
    user = "DATA:\n" + json.dumps(payload, default=str) + "\n\nWrite the answer."
    return complete(_SYSTEM, user, max_tokens=400)
