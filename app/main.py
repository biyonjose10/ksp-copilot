"""FastAPI app. One end-to-end path: detect -> route -> validate -> execute -> synthesize -> verify."""
from __future__ import annotations

import time
import textwrap
from functools import lru_cache

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db import query, reference_lists
from app.templates.registry import REGISTRY
from app.templates.validate import validate
from app.llm import router as router_llm
from app.llm.synthesize import synthesize
from app.llm.verify import verify
from app.i18n.detect import is_kannada, to_english, to_kannada

app = FastAPI(title="KSP Copilot")


class QueryIn(BaseModel):
    text: str
    session_id: str = "demo"
    reply_kn: bool = False


@lru_cache(maxsize=1)
def _refs() -> dict:
    return reference_lists()  # static after seed; safe to cache for the demo


def _refuse(reason: str, suggestion: str | None = None, **extra) -> dict:
    full = reason + (f" {suggestion}" if suggestion else "")
    return {"answer": full, "answer_kn": None, "template_id": None, "resolved_slots": {},
            "rows": [], "citations": [], "refused": True, "refusal_reason": full,
            "sql_executed": "", "timing_ms": {}, **extra}


@app.post("/api/query")
def api_query(body: QueryIn) -> dict:
    timing: dict[str, int] = {}
    lang = "kn" if is_kannada(body.text) else "en"
    want_kn = lang == "kn" or body.reply_kn
    question_en = to_english(body.text) if lang == "kn" else body.text

    t0 = time.perf_counter()
    routed = router_llm.route(question_en)
    timing["route"] = int((time.perf_counter() - t0) * 1000)

    tid = routed.get("template_id")
    if tid is None:
        reason = routed.get("reason", "That question is outside what this system can answer.")
        out = _refuse(f"I can't answer that from the crime database. {reason}",
                      "This tool answers six shapes of question over FIR records; "
                      "ask about cases, counts, trends, or a specific FIR.", timing_ms=timing)
        if want_kn:
            out["answer_kn"] = to_kannada(out["answer"])
        return out

    template = REGISTRY[tid]
    resolved, refusal = validate(template, routed.get("slots", {}), _refs())
    if refusal is not None:
        out = _refuse(refusal.reason, refusal.suggestion, template_id=tid, timing_ms=timing)
        if want_kn:
            out["answer_kn"] = to_kannada(out["answer"])
        return out

    t0 = time.perf_counter()
    rows = query(template.sql, resolved)
    timing["sql"] = int((time.perf_counter() - t0) * 1000)

    citations = [str(r["fir_number"]) for r in rows if r.get("fir_number")]

    t0 = time.perf_counter()
    draft = synthesize(question_en, rows, template.result_kind)
    timing["synth"] = int((time.perf_counter() - t0) * 1000)
    answer, suppressed = verify(draft, rows, question_en)

    return {
        "answer": answer,
        "answer_kn": to_kannada(answer) if want_kn else None,
        "template_id": tid,
        "resolved_slots": {k: v for k, v in resolved.items() if v is not None},
        "rows": rows,
        "citations": citations,
        "refused": False,
        "refusal_reason": None,
        "sql_executed": textwrap.dedent(template.sql).strip(),
        "suppressed": suppressed,
        "timing_ms": timing,
    }


@app.get("/api/health")
def health() -> dict:
    try:
        query("SELECT 1 AS ok")
        return {"status": "ok", "db": "up"}
    except Exception as e:  # noqa: BLE001 — health must report, not raise
        return {"status": "degraded", "db": str(e)}


@app.get("/api/schema")
def schema() -> dict:
    cols = query("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN ('district','division','station','crime_type','officer','fir')
        ORDER BY table_name, ordinal_position
    """)
    tables: dict[str, list[str]] = {}
    for c in cols:
        tables.setdefault(c["table_name"], []).append(c["column_name"])
    return {
        "tables": tables,
        "crime_types": _refs()["crime_labels"],
        "example_questions": [
            "Show me chain-snatching cases near Kengeri in the last six months.",
            "How many vehicle theft FIRs are still open in Bengaluru South division?",
            "Which stations saw the biggest increase in burglary this quarter compared to last?",
            "ಕೆಂಗೇರಿಯಲ್ಲಿ ಕಳೆದ ತಿಂಗಳು ಎಷ್ಟು ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ?",
            "Who was the investigating officer on FIR 0142/2026 at Kengeri station?",
        ],
    }


# Static frontend (single zero-build page) served at the root.
app.mount("/", StaticFiles(directory="web", html=True), name="web")
