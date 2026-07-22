"""Slot validation + refusal paths. No DB needed — reference lists are injected."""
import datetime as dt

from app.templates.registry import REGISTRY
from app.templates import validate as V

REFS = {
    "crime_labels": ["chain snatching", "vehicle theft", "burglary", "cyber fraud"],
    "stations": ["Kengeri", "JP Nagar", "Whitefield", "Yelahanka"],
    "divisions": ["Bengaluru South", "Bengaluru North"],
    "districts": ["Bengaluru City", "Mysuru"],
}


def _ok(tid, slots, refs=REFS):
    resolved, refusal = V.validate(REGISTRY[tid], slots, refs)
    assert refusal is None, refusal
    return resolved


def _refused(tid, slots, refs=REFS):
    resolved, refusal = V.validate(REGISTRY[tid], slots, refs)
    assert resolved is None and refusal is not None
    return refusal


def test_period_resolution_fixed_now():
    assert V.resolve_period("last six months") == (dt.date(2026, 1, 22), dt.date(2026, 7, 22))
    assert V.resolve_period("this quarter") == (dt.date(2026, 7, 1), dt.date(2026, 7, 22))
    assert V.resolve_period("last quarter") == (dt.date(2026, 4, 1), dt.date(2026, 6, 30))
    assert V.resolve_period("last month") == (dt.date(2026, 6, 1), dt.date(2026, 6, 30))


def test_t1_happy_path():
    r = _ok("T1_cases_by_type_area_period",
            {"crime_type": "chain snatching", "period": "last six months", "station": "Kengeri"})
    assert r["crime_type"] == "chain snatching"
    assert r["station"] == "Kengeri"
    assert r["period_start"] == "2026-01-22" and r["period_end"] == "2026-07-22"
    assert r["limit"] == 50
    assert r["division"] is None and r["district"] is None  # unfilled optionals -> NULL


def test_t1_fuzzy_crime_type():
    r = _ok("T1_cases_by_type_area_period",
            {"crime_type": "chain-snatching", "period": "last 6 months"})
    assert r["crime_type"] == "chain snatching"


def test_unknown_crime_refuses_with_suggestions():
    ref = _refused("T1_cases_by_type_area_period",
                   {"crime_type": "unicorn theft", "period": "last month"})
    assert "does not match" in ref.reason


def test_status_normalisation_and_reject():
    assert _ok("T2_count_by_status", {"status": "still open"})["status"] == "open"
    assert _refused("T2_count_by_status", {"status": "pending review"})


def test_ambiguous_area_asks_to_clarify():
    refs = {**REFS, "divisions": ["Bengaluru South", "Mysuru South"]}
    ref = _refused("T2_count_by_status", {"status": "open", "division": "South"}, refs)
    assert ref.needs_clarification is True


def test_start_after_end_refused():
    ref = _refused("T1_cases_by_type_area_period",
                   {"crime_type": "burglary",
                    "period_start": "2026-06-01", "period_end": "2026-01-01"})
    assert "after" in ref.reason


def test_date_floor_clamped():
    r = _ok("T6_top_crime_types", {"period_start": "2020-01-01", "period_end": "2024-06-01"})
    assert r["period_start"] == "2024-01-01"   # clamped to data floor


def test_missing_required_slot_refused():
    assert _refused("T1_cases_by_type_area_period", {"station": "Kengeri"})  # no crime/period


def test_t3_two_periods():
    r = _ok("T3_period_over_period_by_station",
            {"crime_type": "burglary", "period_a": "this quarter", "period_b": "last quarter"})
    assert r["period_a_start"] == "2026-07-01"
    assert r["period_b_start"] == "2026-04-01"


def test_t4_fir_passthrough():
    r = _ok("T4_fir_lookup", {"fir_number": "0142/2026", "station": "Kengeri"})
    assert r["fir_number"] == "0142/2026" and r["station"] == "Kengeri"


def test_limit_clamped():
    r = _ok("T6_top_crime_types",
            {"period": "last year", "limit": 9999})
    assert r["limit"] == 50
