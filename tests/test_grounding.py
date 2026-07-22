"""Grounding check: planted hallucinations must be stripped, real facts kept. No DB."""
from app.llm.verify import verify


def test_hallucinated_fir_stripped():
    rows = [{"fir_number": "0142/2026"}, {"fir_number": "0088/2026"}]
    answer = ("FIR 0142/2026 is a vehicle theft under investigation. "
              "FIR 9999/2026 was filed by the same complainant. "
              "There are 2 matching cases.")
    grounded, suppressed = verify(answer, rows, "test")
    assert "0142/2026" in grounded
    assert "9999/2026" not in grounded
    assert "2 matching cases" in grounded          # real count survives
    assert len(suppressed) == 1


def test_fabricated_count_stripped():
    rows = [{"fir_number": "0001/2026"}, {"fir_number": "0002/2026"}]
    answer = "There are 57 burglary cases in this area."   # 57 != len(rows)==2
    grounded, suppressed = verify(answer, rows, "test")
    assert len(suppressed) == 1
    assert "57" not in grounded


def test_clean_answer_untouched():
    rows = [{"fir_number": "0142/2026", "status": "open"}]
    answer = "FIR 0142/2026 is currently open."
    grounded, suppressed = verify(answer, rows, "test")
    assert grounded == answer
    assert suppressed == []


def test_count_from_column_value_allowed():
    # a comparison result where the count lives in a column, not len(rows)
    rows = [{"station": "Whitefield", "period_a_count": 18, "change": 14}]
    answer = "Whitefield saw 18 burglaries, an increase of 14."
    _grounded, suppressed = verify(answer, rows, "test")
    assert suppressed == []
