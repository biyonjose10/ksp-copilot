"""End-to-end wiring test for /api/query with the two LLM calls stubbed out.

Proves the deterministic path — validate -> execute SQL -> grounding -> response
contract — without needing an API key. Skipped if no seeded DB is reachable.
"""
import pytest

try:
    from app.db import reference_lists
    reference_lists()
    _DB = True
except Exception:  # noqa: BLE001
    _DB = False

pytestmark = pytest.mark.skipif(not _DB, reason="no seeded database reachable")

if _DB:
    from fastapi.testclient import TestClient
    import app.main as main
    client = TestClient(main.app)


def _stub_router(monkeypatch, result):
    monkeypatch.setattr(main.router_llm, "route", lambda q: result)


def test_fir_lookup_end_to_end(monkeypatch):
    _stub_router(monkeypatch, {
        "template_id": "T4_fir_lookup",
        "slots": {"fir_number": "0142/2026", "station": "Kengeri"},
        "confidence": "high"})
    monkeypatch.setattr(main, "synthesize",
                        lambda q, rows, kind: "FIR 0142/2026 is a vehicle theft under investigation.")
    r = client.post("/api/query", json={"text": "who was the IO on FIR 0142/2026 at Kengeri?"})
    d = r.json()
    assert d["refused"] is False
    assert d["template_id"] == "T4_fir_lookup"
    assert "0142/2026" in d["citations"]
    assert d["rows"] and d["rows"][0]["crime_type"] == "vehicle theft"
    assert "SELECT" in d["sql_executed"]
    assert "0142/2026" in d["answer"]


def test_out_of_scope_refuses(monkeypatch):
    _stub_router(monkeypatch, {"template_id": None, "reason": "asks for a prediction"})
    r = client.post("/api/query", json={"text": "is he likely to solve it?"})
    d = r.json()
    assert d["refused"] is True
    assert d["rows"] == []
    assert d["sql_executed"] == ""
    assert d["template_id"] is None


def test_grounding_strips_hallucinated_fir(monkeypatch):
    _stub_router(monkeypatch, {
        "template_id": "T4_fir_lookup",
        "slots": {"fir_number": "0142/2026", "station": "Kengeri"}})
    monkeypatch.setattr(main, "synthesize",
                        lambda q, rows, kind: ("FIR 0142/2026 is a vehicle theft. "
                                               "FIR 9999/2026 was solved yesterday."))
    r = client.post("/api/query", json={"text": "details of FIR 0142/2026"})
    d = r.json()
    assert "9999/2026" not in d["answer"]        # hallucination stripped
    assert "0142/2026" in d["answer"]
    assert len(d["suppressed"]) == 1


def test_bad_crime_type_refuses_before_sql(monkeypatch):
    _stub_router(monkeypatch, {
        "template_id": "T1_cases_by_type_area_period",
        "slots": {"crime_type": "wizardry", "period": "last six months"}})
    r = client.post("/api/query", json={"text": "show wizardry cases last six months"})
    d = r.json()
    assert d["refused"] is True
    assert d["sql_executed"] == ""               # refused at validation, no SQL ran


def test_llm_failure_returns_refusal_not_500(monkeypatch):
    def boom(q):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    monkeypatch.setattr(main.router_llm, "route", boom)
    r = client.post("/api/query", json={"text": "how many cases in Kengeri?"})
    assert r.status_code == 200
    d = r.json()
    assert d["refused"] is True
    assert "temporary error" in d["answer"]


def test_health_and_schema():
    assert client.get("/api/health").json()["status"] == "ok"
    schema = client.get("/api/schema").json()
    assert "fir" in schema["tables"]
    assert "chain snatching" in schema["crime_types"]
