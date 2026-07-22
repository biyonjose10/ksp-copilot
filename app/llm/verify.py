"""Grounding check — pure Python, no LLM. Runs after synthesis, before returning.

Strips any sentence that cites an FIR number or a count not present in the result set,
and logs every suppression. This firing on stage is a FEATURE: it is the answer to
"how do you know it isn't making things up."
"""
from __future__ import annotations

import re
import json
import datetime as dt
from pathlib import Path

_FIR = re.compile(r"\b\d{3,4}/\d{4}\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_COUNT_CLAIM = re.compile(
    r"\b(\d+)\s+(?:cases?|firs?|f\.i\.r\.?s?|records?|reports?|incidents?|complaints?|"
    r"thefts?|burglar\w*|snatch\w*|robber\w*|offences?)\b", re.IGNORECASE)

_LOG = Path(__file__).resolve().parents[2] / "logs" / "grounding.jsonl"


def _allowed_counts(rows: list[dict]) -> set[int]:
    allowed = {len(rows)}
    for row in rows:
        for v in row.values():
            if isinstance(v, int) and not isinstance(v, bool):
                allowed.add(v)
    return allowed


def verify(answer: str, rows: list[dict], question: str = "") -> tuple[str, list[str]]:
    """Return (grounded_answer, suppressed_sentences)."""
    allowed_firs = {str(r["fir_number"]) for r in rows if r.get("fir_number")}
    allowed_counts = _allowed_counts(rows)

    kept, suppressed = [], []
    for sentence in _SENTENCE.split(answer.strip()) if answer.strip() else []:
        bad_fir = [t for t in _FIR.findall(sentence) if t not in allowed_firs]
        bad_count = [int(n) for n in _COUNT_CLAIM.findall(sentence) if int(n) not in allowed_counts]
        if bad_fir or bad_count:
            suppressed.append(sentence)
        else:
            kept.append(sentence)

    grounded = " ".join(kept).strip()
    if suppressed:
        grounded += (" [Note: part of the generated response was suppressed because it "
                     "referenced records or figures not present in the query results.]")
        _log(question, suppressed, allowed_firs)
    return grounded, suppressed


def _log(question: str, suppressed: list[str], allowed_firs: set[str]) -> None:
    try:
        _LOG.parent.mkdir(exist_ok=True)
        with _LOG.open("a") as fh:
            fh.write(json.dumps({
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
                "question": question,
                "suppressed": suppressed,
                "allowed_firs": sorted(allowed_firs),
            }) + "\n")
    except OSError:
        pass  # logging must never break the request


def demo() -> None:
    rows = [{"fir_number": "0142/2026"}, {"fir_number": "0088/2026"}]
    answer = ("FIR 0142/2026 is a vehicle theft. FIR 9999/2026 was solved by the officer. "
              "There are 2 matching cases.")
    grounded, suppressed = verify(answer, rows, "test")
    assert "0142/2026" in grounded
    assert "9999/2026" not in grounded          # planted hallucination stripped
    assert len(suppressed) == 1
    # a real count (2 rows) survives
    assert "2 matching cases" in grounded
    print("verify.demo OK")


if __name__ == "__main__":
    demo()
