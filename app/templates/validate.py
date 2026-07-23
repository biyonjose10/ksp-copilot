"""Slot validation and relative-date resolution. Pure Python, runs before any SQL.

Every failure returns a Refusal (a structured, expected outcome) — never an exception
to the user. Clarifications are Refusals whose `reason` is phrased as a question and
whose `needs_clarification` flag is set.
"""
from __future__ import annotations

import re
import datetime as dt
from dataclasses import dataclass

from rapidfuzz import process, fuzz

from app.config import DEMO_NOW, DATA_FLOOR
from app.templates.registry import QueryTemplate

FUZZY_THRESHOLD = 80
_PLACEHOLDER = re.compile(r"%\((\w+)\)s")
_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


@dataclass(frozen=True)
class Refusal:
    reason: str
    suggestion: str | None = None
    needs_clarification: bool = False


# --- date resolution -------------------------------------------------------

def _month_start(d: dt.date) -> dt.date:
    return d.replace(day=1)


def _add_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    return dt.date(d.year + m // 12, m % 12 + 1, 1)


def _shift_months_keepday(d: dt.date, n: int) -> dt.date:
    """Shift by n months preserving day-of-month (clamped to month length)."""
    m = d.month - 1 + n
    year, month = d.year + m // 12, m % 12 + 1
    last = (_add_months(dt.date(year, month, 1), 1) - dt.timedelta(days=1)).day
    return dt.date(year, month, min(d.day, last))


def _quarter_range(year: int, q: int) -> tuple[dt.date, dt.date]:
    start = dt.date(year, 3 * (q - 1) + 1, 1)
    end = _add_months(start, 3) - dt.timedelta(days=1)
    return start, end


def resolve_period(phrase: str, now: dt.date = DEMO_NOW) -> tuple[dt.date, dt.date] | None:
    """Resolve a relative date phrase to (start, end). Returns None if unrecognised."""
    p = phrase.strip().lower()

    m = re.match(r"(?:last|past|previous)\s+(\w+)\s+(day|week|month|year)s?", p)
    if m:
        n = _WORD_NUM.get(m.group(1)) or (int(m.group(1)) if m.group(1).isdigit() else None)
        if n:
            unit = m.group(2)
            if unit in ("month", "year"):
                return _shift_months_keepday(now, -n * (12 if unit == "year" else 1)), now
            return now - dt.timedelta(days=n * (7 if unit == "week" else 1)), now

    cur_q = (now.month - 1) // 3 + 1
    named = {
        "this month": (_month_start(now), now),
        "last month": (_add_months(_month_start(now), -1), _month_start(now) - dt.timedelta(days=1)),
        "this year": (dt.date(now.year, 1, 1), now),
        "last year": (dt.date(now.year - 1, 1, 1), dt.date(now.year - 1, 12, 31)),
        "this quarter": (_quarter_range(now.year, cur_q)[0], now),
        "last quarter": _quarter_range(now.year if cur_q > 1 else now.year - 1,
                                       cur_q - 1 if cur_q > 1 else 4),
    }
    if p in named:
        return named[p]

    # explicit ISO range "YYYY-MM-DD..YYYY-MM-DD"
    m = re.match(r"(\d{4}-\d{2}-\d{2})\s*(?:to|\.\.|-)\s*(\d{4}-\d{2}-\d{2})", p)
    if m:
        return dt.date.fromisoformat(m.group(1)), dt.date.fromisoformat(m.group(2))
    return None


# --- name resolution -------------------------------------------------------

def resolve_name(value: str, choices: list[str]) -> tuple[str, str | list[str]]:
    """Returns ('ok', canonical) | ('ambiguous', [candidates]) | ('none', [suggestions])."""
    for c in choices:
        if value.strip().lower() == c.lower():
            return "ok", c
    subs = [c for c in choices if value.strip().lower() in c.lower()]
    if len(subs) == 1:
        return "ok", subs[0]
    if len(subs) > 1:
        return "ambiguous", subs
    hit = process.extractOne(value, choices, scorer=fuzz.WRatio)
    if hit and hit[1] >= FUZZY_THRESHOLD:
        return "ok", hit[0]
    near = [h[0] for h in process.extract(value, choices, scorer=fuzz.WRatio, limit=3) if h[1] >= 55]
    return "none", near


# --- main entry point ------------------------------------------------------

def _needed_keys(template: QueryTemplate) -> set[str]:
    return set(_PLACEHOLDER.findall(template.sql))


def validate(template: QueryTemplate, raw: dict, refs: dict) -> tuple[dict, None] | tuple[None, Refusal]:
    """Validate + normalise router slots into DB-ready params, or return a Refusal."""
    resolved: dict = {}

    # crime type — fuzzy match against the taxonomy
    if "crime_type" in raw and raw["crime_type"]:
        status_, val = resolve_name(str(raw["crime_type"]), refs["crime_labels"])
        if status_ != "ok":
            hint = ", ".join(val) if val else "none of the known offence types"
            return None, Refusal(
                f"'{raw['crime_type']}' does not match a known offence type.",
                suggestion=f"Did you mean: {hint}?")
        resolved["crime_type"] = val

    # status — must be a CHECK-constraint value
    valid_status = {"open", "under_investigation", "chargesheeted", "closed", "disposed"}
    if "status" in raw and raw["status"]:
        s = str(raw["status"]).strip().lower().replace(" ", "_")
        s = {"still_open": "open", "pending": "under_investigation"}.get(s, s)
        if s not in valid_status:
            return None, Refusal(f"'{raw['status']}' is not a valid case status.",
                                 suggestion=f"One of: {', '.join(sorted(valid_status))}.")
        resolved["status"] = s

    # hierarchy names — station / division / district
    hierarchy = (("station", "stations"), ("division", "divisions"), ("district", "districts"))
    for field, key in hierarchy:
        if field in raw and raw[field]:
            status_, val = resolve_name(str(raw[field]), refs[key])
            if status_ == "ambiguous":
                return None, Refusal(
                    f"'{raw[field]}' matches more than one {field}. Which did you mean?",
                    suggestion=" / ".join(val), needs_clarification=True)
            if status_ == "none":
                # Router sometimes puts a name at the wrong hierarchy level
                # (e.g. a station in the division slot) — try the other levels.
                for alt_field, alt_key in hierarchy:
                    if alt_field == field or alt_field in resolved:
                        continue
                    alt_status, alt_val = resolve_name(str(raw[field]), refs[alt_key])
                    if alt_status == "ok":
                        resolved[alt_field] = alt_val
                        break
                else:
                    hint = ", ".join(val) if val else f"no known {field}"
                    return None, Refusal(f"'{raw[field]}' does not match a known {field}.",
                                         suggestion=f"Did you mean: {hint}?")
                continue
            resolved[field] = val

    if "fir_number" in raw and raw["fir_number"]:
        resolved["fir_number"] = str(raw["fir_number"]).strip()

    # periods — single, or A/B for period-over-period templates
    def _set_period(prefix: str, phrase_key: str) -> Refusal | None:
        start_k, end_k = f"{prefix}start", f"{prefix}end"
        supplied = [raw.get(k) for k in (phrase_key, start_k, end_k) if raw.get(k)]
        if not supplied:
            return None  # period not supplied (may be optional for this template)
        s = e = None
        if raw.get(start_k) and raw.get(end_k):
            try:
                s = dt.date.fromisoformat(str(raw[start_k]))
                e = dt.date.fromisoformat(str(raw[end_k]))
            except ValueError:
                s = None
        if s is None:
            # Router output varies: the phrase may arrive in the phrase slot or
            # (partially) in start/end. Resolve the first value that parses.
            for v in supplied:
                if (rng := resolve_period(str(v))):
                    s, e = rng
                    break
            else:
                return Refusal(f"Could not interpret the time period '{supplied[0]}'.",
                               suggestion="Try 'last 6 months', 'this quarter', or explicit dates.")
        if s > e:
            return Refusal("The start date is after the end date.")
        if s < DATA_FLOOR:
            s = DATA_FLOOR  # clamp: data starts 2024-01-01
        resolved[start_k], resolved[end_k] = s.isoformat(), e.isoformat()
        return None

    needed = _needed_keys(template)
    if "period_a_start" in needed:  # T3: two periods
        for pfx, ph in (("period_a_", "period_a"), ("period_b_", "period_b")):
            if (r := _set_period(pfx, ph)):
                return None, r
    if "period_start" in needed:
        if (r := _set_period("period_", "period")):
            return None, r

    # limit — clamp to 50
    if "limit" in needed:
        try:
            resolved["limit"] = max(1, min(50, int(raw.get("limit", 50))))
        except (ValueError, TypeError):
            resolved["limit"] = 50

    # required-slot presence check (period_* slots are set by _set_period above)
    for slot in template.required_slots:
        if slot not in resolved:
            return None, Refusal(f"Missing required detail: {slot.replace('_', ' ')}.",
                                 suggestion="Please include it in your question.")

    # fill remaining placeholders the SQL references with NULL (optional, absent)
    for k in needed:
        resolved.setdefault(k, None)

    return resolved, None


def demo() -> None:
    """Self-check for the non-trivial logic: date resolution + name resolution."""
    # relative dates resolve against fixed DEMO_NOW = 2026-07-22
    assert resolve_period("last six months") == (dt.date(2026, 1, 22), dt.date(2026, 7, 22))
    assert resolve_period("last month") == (dt.date(2026, 6, 1), dt.date(2026, 6, 30))
    assert resolve_period("this quarter") == (dt.date(2026, 7, 1), dt.date(2026, 7, 22))
    assert resolve_period("last quarter") == (dt.date(2026, 4, 1), dt.date(2026, 6, 30))
    assert resolve_period("2024-03-01..2024-04-01") == (dt.date(2024, 3, 1), dt.date(2024, 4, 1))
    assert resolve_period("banana") is None

    stations = ["Kengeri", "JP Nagar", "Whitefield", "Yelahanka"]
    assert resolve_name("kengeri", stations) == ("ok", "Kengeri")
    assert resolve_name("Kengri", stations)[0] == "ok"       # fuzzy
    assert resolve_name("Atlantis", stations)[0] == "none"
    assert resolve_name("nagar", ["JP Nagar", "Yelahanka Nagar"])[0] == "ambiguous"
    print("validate.demo OK")


if __name__ == "__main__":
    demo()
