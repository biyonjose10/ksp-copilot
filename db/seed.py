"""Deterministic synthetic seed for the KSP Copilot demo database.

ALL DATA IS SYNTHETIC. No real KSP records are used. Regenerate with:

    python db/seed.py            # applies schema.sql then seeds

Reproducible: random.seed(26072026). Signals planted for the five demo questions
(chain-snatching cluster near Kengeri, burglary uptick this quarter, FIR 0142/2026).
"""
from __future__ import annotations

import os
import random
import datetime as dt
from pathlib import Path

import psycopg

SEED = 26072026
DATA_FLOOR = dt.date(2024, 1, 1)
DATA_CEIL = dt.date(2026, 7, 22)  # == DEMO_NOW
DB_URL = os.environ.get("DATABASE_URL", "postgresql://ksp:ksp@localhost:5432/ksp")

random.seed(SEED)

# --- reference data --------------------------------------------------------
# (district, division, station, lat, lon). Kengeri / Bengaluru South are load-bearing.
STATIONS = [
    ("Bengaluru City", "Bengaluru South", "Kengeri",            12.9081, 77.4822),
    ("Bengaluru City", "Bengaluru South", "Rajarajeshwari Nagar", 12.9257, 77.5197),
    ("Bengaluru City", "Bengaluru South", "Jnanabharathi",      12.9420, 77.5040),
    ("Bengaluru City", "Bengaluru South", "Kumaraswamy Layout", 12.9080, 77.5620),
    ("Bengaluru City", "Bengaluru South", "Banashankari",       12.9250, 77.5460),
    ("Bengaluru City", "Bengaluru South", "JP Nagar",           12.9070, 77.5850),
    ("Bengaluru City", "Bengaluru Central", "Cubbon Park",      12.9760, 77.5920),
    ("Bengaluru City", "Bengaluru Central", "Commercial Street",12.9820, 77.6090),
    ("Bengaluru City", "Bengaluru Central", "Vidhana Soudha",   12.9800, 77.5910),
    ("Bengaluru City", "Bengaluru Central", "Shivajinagar",     12.9860, 77.6050),
    ("Bengaluru City", "Bengaluru East", "Whitefield",          12.9698, 77.7500),
    ("Bengaluru City", "Bengaluru East", "Marathahalli",        12.9560, 77.7010),
    ("Bengaluru City", "Bengaluru East", "KR Puram",            13.0080, 77.6960),
    ("Bengaluru City", "Bengaluru East", "Indiranagar",         12.9719, 77.6412),
    ("Bengaluru City", "Bengaluru North", "Yelahanka",          13.1007, 77.5963),
    ("Bengaluru City", "Bengaluru North", "Hebbal",             13.0358, 77.5970),
    ("Bengaluru City", "Bengaluru North", "Peenya",             13.0280, 77.5190),
    ("Bengaluru City", "Bengaluru North", "Yeshwanthpur",       13.0280, 77.5540),
    ("Bengaluru City", "Bengaluru West", "Rajajinagar",         12.9910, 77.5520),
    ("Bengaluru City", "Bengaluru West", "Vijayanagar",         12.9720, 77.5330),
    ("Bengaluru City", "Bengaluru West", "Magadi Road",         12.9760, 77.5560),
    ("Bengaluru City", "Bengaluru West", "Basaveshwaranagar",   12.9910, 77.5370),
    ("Bengaluru Rural", "Bengaluru Rural North", "Devanahalli", 13.2437, 77.7126),
    ("Bengaluru Rural", "Bengaluru Rural North", "Doddaballapura", 13.2920, 77.5370),
    ("Bengaluru Rural", "Bengaluru Rural North", "Nelamangala", 13.0997, 77.3936),
    ("Bengaluru Rural", "Bengaluru Rural South", "Anekal",      12.7110, 77.6960),
    ("Bengaluru Rural", "Bengaluru Rural South", "Attibele",    12.7830, 77.7710),
    ("Bengaluru Rural", "Bengaluru Rural South", "Sarjapura",   12.8580, 77.7870),
    ("Bengaluru Rural", "Bengaluru Rural South", "Hoskote",     13.0707, 77.7980),
    ("Mysuru", "Mysuru City", "Devaraja",                       12.3070, 76.6540),
    ("Mysuru", "Mysuru City", "Lashkar",                        12.3090, 76.6480),
    ("Mysuru", "Mysuru City", "Vijayanagar Mysuru",            12.3220, 76.6110),
    ("Mysuru", "Mysuru City", "Nazarbad",                       12.2990, 76.6690),
    ("Mysuru", "Mysuru Rural", "Hunsur",                        12.3040, 76.2930),
    ("Mysuru", "Mysuru Rural", "Nanjangud",                     12.1180, 76.6830),
    ("Mysuru", "Mysuru Rural", "T Narasipura",                  12.2110, 76.8970),
    ("Mysuru", "Mysuru Rural", "KR Nagar",                      12.4230, 76.3860),
    ("Mysuru", "Mysuru Rural", "Periyapatna",                   12.3350, 76.0980),
    ("Mysuru", "Mysuru Rural", "Saligrama",                     12.5620, 76.2600),
    ("Mysuru", "Mysuru Rural", "Bannur",                        12.3350, 76.8680),
]

CRIME_TYPES = [
    # label, category, statute (BNS), legacy (IPC)
    ("chain snatching",   "property", "BNS 304(2)", "IPC 379"),
    ("vehicle theft",     "property", "BNS 303(2)", "IPC 379"),
    ("burglary",          "property", "BNS 305",    "IPC 457"),
    ("house theft",       "property", "BNS 305",    "IPC 380"),
    ("robbery",           "property", "BNS 309",    "IPC 392"),
    ("cheating",          "property", "BNS 318",    "IPC 420"),
    ("cyber fraud",       "cyber",    "BNS 318(4)", "IT Act 66D"),
    ("assault",           "body",     "BNS 115",    "IPC 323"),
    ("hurt",              "body",     "BNS 117",    "IPC 324"),
    ("criminal intimidation","body",  "BNS 351",    "IPC 506"),
    ("rash driving",      "traffic",  "BNS 281",    "IPC 279"),
    ("drunken driving",   "traffic",  "MV Act 185", None),
]

FIRST = ["Suresh","Ramesh","Prakash","Manjunath","Girish","Anand","Vinay","Kiran",
         "Lakshmi","Divya","Nagaraj","Shivakumar","Roopa","Pallavi","Harish","Basavaraj",
         "Deepa","Chandan","Rekha","Mohan","Gowtham","Sneha","Yashwanth","Bhavana"]
LAST = ["Gowda","Reddy","Rao","Nayak","Shetty","Hegde","Kumar","Patil","Naidu","Murthy",
        "Bhat","Achar","Poojary","Kulkarni","Desai","Iyer"]
RANKS = ["PSI", "PSI", "PSI", "PI", "PI", "ASI", "ACP"]

STATUSES = ["open", "under_investigation", "chargesheeted", "closed", "disposed"]
STATUS_WEIGHTS = [18, 30, 22, 20, 10]

SUMMARIES = {
    "chain snatching": "Complainant reported a gold chain snatched by two men on a motorcycle.",
    "vehicle theft":   "A two-wheeler parked overnight was found missing the next morning.",
    "burglary":        "House lock broken during the day; cash and jewellery reported stolen.",
    "house theft":     "Items reported missing from the residence after the family returned.",
    "robbery":         "Complainant robbed of cash and mobile phone at knife-point.",
    "cheating":        "Complainant paid an advance for goods that were never delivered.",
    "cyber fraud":     "Complainant transferred money after a fraudulent call impersonating a bank.",
    "assault":         "Dispute between neighbours escalated into a physical altercation.",
    "hurt":            "Complainant sustained injuries during a quarrel over parking.",
    "criminal intimidation": "Complainant received threatening messages demanding money.",
    "rash driving":    "Vehicle driven in a rash and negligent manner endangering pedestrians.",
    "drunken driving": "Driver stopped at a checkpoint and found to be under the influence.",
}


def rand_date(start: dt.date, end: dt.date) -> dt.date:
    return start + dt.timedelta(days=random.randint(0, (end - start).days))


def jitter(base: float, km: float = 3.0) -> float:
    return round(base + random.uniform(-km, km) / 111.0, 6)


def main() -> None:
    schema_sql = (Path(__file__).parent / "schema.sql").read_text()
    with psycopg.connect(DB_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(schema_sql)

        # districts / divisions / stations
        district_ids: dict[str, int] = {}
        division_ids: dict[tuple[str, str], int] = {}
        station_rows: list[tuple[int, str, float, float]] = []  # (station_id, name, lat, lon)
        for district, division, station, lat, lon in STATIONS:
            if district not in district_ids:
                cur.execute("INSERT INTO district(name) VALUES (%s) RETURNING district_id", (district,))
                district_ids[district] = cur.fetchone()[0]
            key = (district, division)
            if key not in division_ids:
                cur.execute(
                    "INSERT INTO division(district_id, name) VALUES (%s,%s) RETURNING division_id",
                    (district_ids[district], division),
                )
                division_ids[key] = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO station(division_id, name, latitude, longitude) VALUES (%s,%s,%s,%s) RETURNING station_id",
                (division_ids[key], station, lat, lon),
            )
            station_rows.append((cur.fetchone()[0], station, lat, lon))

        # crime types
        crime_ids: dict[str, int] = {}
        for label, cat, statute, legacy in CRIME_TYPES:
            cur.execute(
                "INSERT INTO crime_type(label, category, statute_section, legacy_section) VALUES (%s,%s,%s,%s) RETURNING crime_type_id",
                (label, cat, statute, legacy),
            )
            crime_ids[label] = cur.fetchone()[0]

        # officers: 2-4 per station
        station_officers: dict[int, list[int]] = {}
        for sid, _sname, _, _ in station_rows:
            ids = []
            for _ in range(random.randint(2, 4)):
                name = f"{random.choice(FIRST)} {random.choice(LAST)}"
                cur.execute(
                    "INSERT INTO officer(name, rank, station_id) VALUES (%s,%s,%s) RETURNING officer_id",
                    (name, random.choice(RANKS), sid),
                )
                ids.append(cur.fetchone()[0])
            station_officers[sid] = ids

        # per (station, year) running FIR sequence number
        seq: dict[tuple[int, int], int] = {}

        def next_number(sid: int, year: int) -> str:
            n = seq.get((sid, year), 0) + 1
            seq[(sid, year)] = n
            return f"{n:04d}/{year}"

        def insert_fir(sid, ct_label, reg: dt.date, status=None, io=None,
                       occurred=None, coords=True, forced_number=None):
            number = forced_number or next_number(sid, reg.year)
            status = status or random.choices(STATUSES, STATUS_WEIGHTS)[0]
            io = io if io is not None else random.choice(station_officers[sid])
            if occurred is None and random.random() > 0.03:
                occurred = reg - dt.timedelta(days=random.randint(0, 5))
            base = next(s for s in station_rows if s[0] == sid)
            lat = jitter(base[2]) if coords and random.random() > 0.02 else None
            lon = jitter(base[3]) if coords and lat is not None else None
            cur.execute(
                """INSERT INTO fir(fir_number, station_id, crime_type_id, registered_on,
                                   occurred_on, status, io_officer_id, latitude, longitude, summary)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (station_id, fir_number) DO NOTHING""",
                (number, sid, crime_ids[ct_label], reg, occurred, status, io, lat, lon,
                 SUMMARIES[ct_label]),
            )

        sids = [s[0] for s in station_rows]
        kengeri_id = next(s[0] for s in station_rows if s[1] == "Kengeri")

        # --- 1. baseline ~5800 FIRs, uniform over the window --------------
        for _ in range(5800):
            insert_fir(random.choice(sids), random.choice(list(crime_ids)),
                       rand_date(DATA_FLOOR, DATA_CEIL))

        # --- 2. planted: chain-snatching cluster near Kengeri, last 6 mo --
        window_start = DATA_CEIL - dt.timedelta(days=182)
        for _ in range(28):
            insert_fir(kengeri_id, "chain snatching", rand_date(window_start, DATA_CEIL))

        # --- 3. planted: burglary uptick this quarter (Jul 2026) at 3 stns-
        q3_start = dt.date(2026, 7, 1)
        for sid in [next(s[0] for s in station_rows if s[1] == n)
                    for n in ("Whitefield", "JP Nagar", "Yelahanka")]:
            for _ in range(random.randint(14, 20)):
                insert_fir(sid, "burglary", rand_date(q3_start, DATA_CEIL))
            # modest Q2 baseline so the increase is real, not division-by-zero
            for _ in range(random.randint(3, 6)):
                insert_fir(sid, "burglary", rand_date(dt.date(2026, 4, 1), dt.date(2026, 6, 30)))

        # --- 4. planted: stale open cases (>18 months old, still open) ----
        for _ in range(20):
            insert_fir(random.choice(sids), random.choice(list(crime_ids)),
                       rand_date(DATA_FLOOR, dt.date(2024, 12, 31)), status="open")

        # --- 5. forced: FIR 0142/2026 at Kengeri, vehicle theft, named IO -
        io = station_officers[kengeri_id][0]
        cur.execute("UPDATE officer SET name='Manjunath Gowda', rank='PSI' WHERE officer_id=%s", (io,))
        insert_fir(kengeri_id, "vehicle theft", dt.date(2026, 3, 14),
                   status="under_investigation", io=io,
                   occurred=dt.date(2026, 3, 13), forced_number="0142/2026")

        cur.execute("SELECT count(*) FROM fir")
        total = cur.fetchone()[0]
        cur.execute("SELECT fir_number FROM fir WHERE station_id=%s AND fir_number='0142/2026'",
                    (kengeri_id,))
        assert cur.fetchone(), "FIR 0142/2026 was not planted"
        print(f"Seeded {total} FIRs across {len(station_rows)} stations. FIR 0142/2026 OK.")


if __name__ == "__main__":
    main()
