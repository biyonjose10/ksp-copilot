"""Each template executed against the seeded DB with hardcoded slots.

Skipped automatically if no database is reachable (so the pure-Python suites still run
in CI without Postgres). Run `python db/seed.py` first for these to pass.
"""
import pytest

try:
    from app.db import query, reference_lists
    reference_lists()  # forces a connection + confirms data is present
    _DB = True
except Exception:  # noqa: BLE001
    _DB = False

pytestmark = pytest.mark.skipif(not _DB, reason="no seeded database reachable")

if _DB:
    from app.templates.registry import REGISTRY
    from app.templates.validate import validate

    REFS = reference_lists()

    def _run(tid, slots):
        resolved, refusal = validate(REGISTRY[tid], slots, REFS)
        assert refusal is None, refusal
        return query(REGISTRY[tid].sql, resolved)


def test_t4_fir_0142_lookup():
    rows = _run("T4_fir_lookup", {"fir_number": "0142/2026", "station": "Kengeri"})
    assert len(rows) == 1
    r = rows[0]
    assert r["crime_type"] == "vehicle theft"
    assert r["station"] == "Kengeri"
    assert r["io_name"]  # a named investigating officer exists


def test_t1_chain_snatching_near_kengeri():
    rows = _run("T1_cases_by_type_area_period",
                {"crime_type": "chain snatching", "period": "last six months", "station": "Kengeri"})
    assert len(rows) > 0
    assert all(r["crime_type"] == "chain snatching" for r in rows)
    assert all(r["station"] == "Kengeri" for r in rows)


def test_t2_open_vehicle_thefts_bengaluru_south():
    rows = _run("T2_count_by_status",
                {"status": "open", "crime_type": "vehicle theft", "division": "Bengaluru South"})
    assert rows[0]["count"] >= 0  # scalar shape


def test_t3_burglary_quarter_over_quarter():
    rows = _run("T3_period_over_period_by_station",
                {"crime_type": "burglary", "period_a": "this quarter", "period_b": "last quarter"})
    assert len(rows) > 0
    # the planted uptick stations should top the ranking
    top = {r["station"] for r in rows[:5]}
    assert top & {"Whitefield", "JP Nagar", "Yelahanka"}
    assert rows[0]["change"] >= rows[-1]["change"]  # ordered by change desc


def test_t5_station_summary():
    rows = _run("T5_station_summary", {"station": "Kengeri"})
    assert len(rows) > 0
    assert {"crime_type", "status", "count"} <= set(rows[0].keys())


def test_t6_top_crime_types():
    rows = _run("T6_top_crime_types", {"period": "last year", "division": "Bengaluru South"})
    assert len(rows) > 0
    counts = [r["count"] for r in rows]
    assert counts == sorted(counts, reverse=True)  # ranked
