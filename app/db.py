"""Thin psycopg3 connection pool + a dict-returning query helper."""
from __future__ import annotations

from typing import Any

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

from app.config import DB_URL

_pool = ConnectionPool(DB_URL, min_size=1, max_size=4, open=True)


def query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a parameterised SELECT, return rows as dicts. params uses %(name)s placeholders."""
    with _pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or {})
        return cur.fetchall()


def reference_lists() -> dict[str, Any]:
    """Load the small lookup sets the validator needs (crime labels + hierarchy names)."""
    labels = [r["label"] for r in query("SELECT label FROM crime_type ORDER BY label")]
    stations = query("""
        SELECT s.name AS station, dv.name AS division, dt.name AS district
        FROM station s
        JOIN division dv ON dv.division_id = s.division_id
        JOIN district dt ON dt.district_id = dv.district_id
        ORDER BY s.name
    """)
    return {
        "crime_labels": labels,
        "stations": [r["station"] for r in stations],
        "divisions": sorted({r["division"] for r in stations}),
        "districts": sorted({r["district"] for r in stations}),
    }
