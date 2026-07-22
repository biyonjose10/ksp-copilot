"""Fixed registry of parameterised query templates.

The LLM NEVER writes SQL. It picks a template_id and fills slots; Python validates
the slots and executes the hand-written SQL below. Every %(name)s is bound as a
parameter — no string interpolation of user input, ever.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class QueryTemplate:
    template_id: str
    description: str          # shown to the LLM in the router prompt
    required_slots: tuple[str, ...]
    optional_slots: tuple[str, ...]
    sql: str                  # %(named)s placeholders only
    result_kind: Literal["rows", "scalar", "comparison"]


T1 = QueryTemplate(
    template_id="T1_cases_by_type_area_period",
    description=(
        "Retrieve individual FIR records filtered by crime type, geographic area, "
        "and a date range. Use when the user wants to SEE the cases, not count them."
    ),
    required_slots=("crime_type", "period_start", "period_end"),
    optional_slots=("station", "division", "district", "limit"),
    sql="""
        SELECT f.fir_id, f.fir_number, s.name AS station, ct.label AS crime_type,
               f.registered_on, f.status, f.summary
        FROM fir f
        JOIN station s      ON s.station_id = f.station_id
        JOIN division dv    ON dv.division_id = s.division_id
        JOIN district dt    ON dt.district_id = dv.district_id
        JOIN crime_type ct  ON ct.crime_type_id = f.crime_type_id
        WHERE ct.label = %(crime_type)s
          AND f.registered_on BETWEEN %(period_start)s AND %(period_end)s
          AND (%(station)s::text  IS NULL OR s.name  = %(station)s)
          AND (%(division)s::text IS NULL OR dv.name = %(division)s)
          AND (%(district)s::text IS NULL OR dt.name = %(district)s)
        ORDER BY f.registered_on DESC
        LIMIT %(limit)s
    """,
    result_kind="rows",
)

T2 = QueryTemplate(
    template_id="T2_count_by_status",
    description=(
        "Count FIRs matching a case status (e.g. 'open', 'under_investigation'), "
        "optionally narrowed by crime type, area and date range. Use to answer "
        "'how many ... are still open / closed'."
    ),
    required_slots=("status",),
    optional_slots=("crime_type", "division", "district", "station",
                    "period_start", "period_end"),
    sql="""
        SELECT count(*) AS count
        FROM fir f
        JOIN station s      ON s.station_id = f.station_id
        JOIN division dv    ON dv.division_id = s.division_id
        JOIN district dt    ON dt.district_id = dv.district_id
        JOIN crime_type ct  ON ct.crime_type_id = f.crime_type_id
        WHERE f.status = %(status)s
          AND (%(crime_type)s::text   IS NULL OR ct.label = %(crime_type)s)
          AND (%(station)s::text      IS NULL OR s.name   = %(station)s)
          AND (%(division)s::text     IS NULL OR dv.name  = %(division)s)
          AND (%(district)s::text     IS NULL OR dt.name  = %(district)s)
          AND (%(period_start)s::date IS NULL OR f.registered_on >= %(period_start)s)
          AND (%(period_end)s::date   IS NULL OR f.registered_on <= %(period_end)s)
    """,
    result_kind="scalar",
)

T3 = QueryTemplate(
    template_id="T3_period_over_period_by_station",
    description=(
        "Compare counts of a crime type per station between two date ranges "
        "(period A vs period B) and rank stations by the change. Use for "
        "'which stations saw the biggest increase / decrease ... this quarter vs last'."
    ),
    required_slots=("crime_type", "period_a_start", "period_a_end",
                    "period_b_start", "period_b_end"),
    optional_slots=("division", "district", "limit"),
    sql="""
        WITH a AS (
            SELECT f.station_id, count(*) AS n
            FROM fir f JOIN crime_type ct ON ct.crime_type_id = f.crime_type_id
            WHERE ct.label = %(crime_type)s
              AND f.registered_on BETWEEN %(period_a_start)s AND %(period_a_end)s
            GROUP BY f.station_id
        ),
        b AS (
            SELECT f.station_id, count(*) AS n
            FROM fir f JOIN crime_type ct ON ct.crime_type_id = f.crime_type_id
            WHERE ct.label = %(crime_type)s
              AND f.registered_on BETWEEN %(period_b_start)s AND %(period_b_end)s
            GROUP BY f.station_id
        )
        SELECT s.name AS station,
               COALESCE(a.n, 0) AS period_a_count,
               COALESCE(b.n, 0) AS period_b_count,
               COALESCE(a.n, 0) - COALESCE(b.n, 0) AS change
        FROM a
        FULL OUTER JOIN b ON a.station_id = b.station_id
        JOIN station s   ON s.station_id = COALESCE(a.station_id, b.station_id)
        JOIN division dv ON dv.division_id = s.division_id
        JOIN district dt ON dt.district_id = dv.district_id
        WHERE (%(division)s::text IS NULL OR dv.name = %(division)s)
          AND (%(district)s::text IS NULL OR dt.name = %(district)s)
        ORDER BY change DESC
        LIMIT %(limit)s
    """,
    result_kind="comparison",
)

T4 = QueryTemplate(
    template_id="T4_fir_lookup",
    description=(
        "Look up a single FIR by its number (e.g. '0142/2026'), returning its "
        "crime type, status, dates, station and investigating officer. Use for "
        "'who was the IO on FIR ...', 'what is the status of FIR ...'."
    ),
    required_slots=("fir_number",),
    optional_slots=("station",),
    sql="""
        SELECT f.fir_number, s.name AS station, ct.label AS crime_type,
               f.registered_on, f.occurred_on, f.status, f.summary,
               o.name AS io_name, o.rank AS io_rank
        FROM fir f
        JOIN station s      ON s.station_id = f.station_id
        JOIN crime_type ct  ON ct.crime_type_id = f.crime_type_id
        LEFT JOIN officer o ON o.officer_id = f.io_officer_id
        WHERE f.fir_number = %(fir_number)s
          AND (%(station)s::text IS NULL OR s.name = %(station)s)
        ORDER BY f.registered_on DESC
        LIMIT %(limit)s
    """,
    result_kind="rows",
)

T5 = QueryTemplate(
    template_id="T5_station_summary",
    description=(
        "Summarise the caseload at one station: counts by status and by crime type, "
        "optionally within a date range. Use for 'what's the caseload / case mix at ... station'."
    ),
    required_slots=("station",),
    optional_slots=("period_start", "period_end"),
    sql="""
        SELECT ct.label AS crime_type, f.status, count(*) AS count
        FROM fir f
        JOIN station s      ON s.station_id = f.station_id
        JOIN crime_type ct  ON ct.crime_type_id = f.crime_type_id
        WHERE s.name = %(station)s
          AND (%(period_start)s::date IS NULL OR f.registered_on >= %(period_start)s)
          AND (%(period_end)s::date   IS NULL OR f.registered_on <= %(period_end)s)
        GROUP BY ct.label, f.status
        ORDER BY count DESC
        LIMIT %(limit)s
    """,
    result_kind="rows",
)

T6 = QueryTemplate(
    template_id="T6_top_crime_types",
    description=(
        "Rank the most common crime types over a date range, optionally within an "
        "area. Use for 'most common crimes in ... last month', 'top offences in ...'."
    ),
    required_slots=("period_start", "period_end"),
    optional_slots=("division", "district", "station", "limit"),
    sql="""
        SELECT ct.label AS crime_type, count(*) AS count
        FROM fir f
        JOIN station s      ON s.station_id = f.station_id
        JOIN division dv    ON dv.division_id = s.division_id
        JOIN district dt    ON dt.district_id = dv.district_id
        JOIN crime_type ct  ON ct.crime_type_id = f.crime_type_id
        WHERE f.registered_on BETWEEN %(period_start)s AND %(period_end)s
          AND (%(station)s::text  IS NULL OR s.name  = %(station)s)
          AND (%(division)s::text IS NULL OR dv.name = %(division)s)
          AND (%(district)s::text IS NULL OR dt.name = %(district)s)
        GROUP BY ct.label
        ORDER BY count DESC
        LIMIT %(limit)s
    """,
    result_kind="rows",
)

REGISTRY: dict[str, QueryTemplate] = {t.template_id: t for t in (T1, T2, T3, T4, T5, T6)}
