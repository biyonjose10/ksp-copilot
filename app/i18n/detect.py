"""Language detection + translation for the Kannada input/output path.

Only the input and the final answer are translated. Routing, validation and SQL all
run in English. FIR numbers, station names and officer names are never translated.
"""
from __future__ import annotations

import re

from app.llm.client import complete
from app.i18n.stations_kn import apply_station_map

_KANNADA = re.compile(r"[ಀ-೿]")


def is_kannada(text: str) -> bool:
    return bool(_KANNADA.search(text))


def to_english(text: str) -> str:
    """Translate a Kannada query to English, keeping proper nouns intact."""
    pre = apply_station_map(text)          # pin station/area names first
    if not is_kannada(pre):
        return pre                         # nothing left to translate
    return complete(
        "Translate this Karnataka police query from Kannada to English. Keep any English "
        "words, FIR numbers, station names and proper nouns exactly as-is. Reply with the "
        "translation only.",
        pre, max_tokens=200)


def to_kannada(text: str) -> str:
    """Translate an English answer back to Kannada, leaving identifiers untranslated."""
    return complete(
        "Translate this police answer from English to Kannada. Do NOT translate FIR "
        "numbers (like 0142/2026), station names, or officer names — leave them in the "
        "Latin script exactly as written. Reply with the translation only.",
        text, max_tokens=500)
