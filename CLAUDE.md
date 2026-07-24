# CLAUDE.md — KSP Datathon 2026 / Track 1 Build Spec

**Project codename:** `ksp-copilot`
**Team:** Triple T (Biyon Jose — lead; Andrea; Rayan; Banit)
**Track:** Conversational AI for the KSP Crime Database
**Prototype deadline:** 26 July 2026
**Finale:** Bengaluru, 26 September 2026
**Deployment target:** Zoho Catalyst (promo code `KSPH26`)

---

## 0. Read this first (agent instructions)

You are building a **demo-grade but architecturally honest** prototype in **four days**. Optimise for:

1. **One end-to-end path that never breaks** over five half-working features.
2. **Correctness and refusal** over coverage. A confidently wrong answer about a criminal case is disqualifying in front of a law-enforcement jury.
3. **Legibility to a non-technical judge.** Every answer must show its work.

### Hard rules — do not violate

- **DO NOT generate free-form SQL from the LLM.** The LLM selects and fills a *parameterised template* from a fixed registry. This is the single most important architectural constraint in this document. See §4.
- **DO NOT invent data.** Every factual claim in an answer must carry a record ID that exists in the result set.
- **DO NOT use real police data.** Use only the synthetic generator in §3. No scraping, no real FIR text.
- **DO NOT add auth, multi-tenancy, or user management.** Out of scope. Single hardcoded demo user.
- **DO NOT reach for LangChain / LlamaIndex / agent frameworks.** Plain `httpx` calls to the model API. The team must be able to explain every line to a judge.
- **DO NOT write tests for the frontend.** Backend query layer only. Time is the constraint.

### When you are unsure

Stop and leave a `# TODO(team):` comment with a one-line question rather than guessing at police-domain semantics. Getting jurisdiction hierarchy or IPC/BNS section mapping subtly wrong is worse than leaving it flagged.

---

## 1. The problem, stated properly

Karnataka State Police hold large volumes of structured crime records (FIRs, accused persons, complainants, case status, station/jurisdiction hierarchy). Officers who need answers from this data currently need either a trained analyst or knowledge of the query interface.

**We are building:** a natural-language query layer over that structured data, which returns *cited, verifiable* answers and explicitly refuses when the data cannot support an answer.

**We are NOT building:**
- A predictive policing / hotspot forecasting system (different track, and ethically fraught in a 4-day build).
- A document RAG system over unstructured case files. The data here is *structured*. Treat it as such.
- Anything that scores or profiles individuals.

### The demo question set (build backwards from these)

These five must work flawlessly. Everything else is a bonus.

1. "Show me chain-snatching cases near Kengeri in the last six months."
2. "How many vehicle theft FIRs are still open in Bengaluru South division?"
3. "Which stations saw the biggest increase in burglary this quarter compared to last?"
4. "ಕೆಂಗೇರಿಯಲ್ಲಿ ಕಳೆದ ತಿಂಗಳು ಎಷ್ಟು ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ?" (Kannada: how many cases registered in Kengeri last month?)
5. "Who was the investigating officer on FIR 0142/2026 at Kengeri station?" — then a deliberate follow-up the data **cannot** answer, e.g. "Is he likely to solve it?" → must refuse cleanly.

Question 5's refusal is a scoring moment, not a failure. Rehearse it.

---

## 2. Architecture

```
┌─────────────┐
│  React UI   │  chat panel + result table + citation drawer
└──────┬──────┘
       │ POST /api/query  {text, session_id}
┌──────▼───────────────────────────────────────────┐
│  FastAPI backend                                 │
│                                                  │
│  1. Language detect  (kn → translate to en)      │
│  2. Intent router    → template_id + slots       │  ← LLM call #1 (constrained)
│  3. Slot validation  → reject/clarify if bad     │  ← pure Python, no LLM
│  4. Template execute → parameterised SQL         │  ← no LLM
│  5. Answer synthesis → prose + citations         │  ← LLM call #2 (grounded)
│  6. Refusal check    → drop ungrounded claims    │  ← pure Python
└──────┬───────────────────────────────────────────┘
       │
┌──────▼──────┐
│ PostgreSQL  │  synthetic KSP-shaped schema
└─────────────┘
```

**Why two LLM calls and not one:** step 2 is a *classification* problem with a closed output space. Step 5 is a *summarisation* problem over data already retrieved. Collapsing them into one call is how teams end up with hallucinated case numbers. Keep them separate.

### Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Team knows it; Catalyst supports it |
| DB | PostgreSQL 15 | Banit's SQL depth; window functions for §4 templates |
| DB access | `psycopg` 3 + raw parameterised SQL | No ORM. Judges can read the queries. |
| LLM | Anthropic Messages API via `httpx` | No framework indirection |
| Frontend | React + Vite + Tailwind | Fast; single page |
| Deploy | Zoho Catalyst (`KSPH26`) | Sponsor-aligned; likely scored |

---

## 3. Data layer

### 3.1 Schema

Create `db/schema.sql`. This shape mirrors how Indian police records actually decompose. Keep the names.

```sql
CREATE TABLE district (
    district_id     SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE
);

CREATE TABLE division (
    division_id     SERIAL PRIMARY KEY,
    district_id     INT NOT NULL REFERENCES district(district_id),
    name            TEXT NOT NULL,
    UNIQUE (district_id, name)
);

CREATE TABLE station (
    station_id      SERIAL PRIMARY KEY,
    division_id     INT NOT NULL REFERENCES division(division_id),
    name            TEXT NOT NULL,
    latitude        NUMERIC(9,6) NOT NULL,
    longitude       NUMERIC(9,6) NOT NULL,
    UNIQUE (division_id, name)
);

-- Offence taxonomy. crime_type is the user-facing label;
-- statute_section is the legal hook (BNS 2023, with legacy IPC noted).
CREATE TABLE crime_type (
    crime_type_id   SERIAL PRIMARY KEY,
    label           TEXT NOT NULL UNIQUE,     -- 'chain snatching'
    category        TEXT NOT NULL,            -- 'property' | 'body' | 'cyber' | 'traffic'
    statute_section TEXT,                     -- 'BNS 304(2)'
    legacy_section  TEXT                      -- 'IPC 379' (nullable)
);

CREATE TABLE officer (
    officer_id      SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    rank            TEXT NOT NULL,            -- 'PSI' | 'PI' | 'ACP' ...
    station_id      INT NOT NULL REFERENCES station(station_id)
);

CREATE TABLE fir (
    fir_id          SERIAL PRIMARY KEY,
    fir_number      TEXT NOT NULL,            -- '0142/2026'
    station_id      INT NOT NULL REFERENCES station(station_id),
    crime_type_id   INT NOT NULL REFERENCES crime_type(crime_type_id),
    registered_on   DATE NOT NULL,
    occurred_on     DATE,
    status          TEXT NOT NULL
                    CHECK (status IN ('open','under_investigation','chargesheeted','closed','disposed')),
    io_officer_id   INT REFERENCES officer(officer_id),
    latitude        NUMERIC(9,6),
    longitude       NUMERIC(9,6),
    summary         TEXT,                     -- 1-2 synthetic sentences
    UNIQUE (station_id, fir_number)
);

CREATE INDEX idx_fir_registered_on ON fir(registered_on);
CREATE INDEX idx_fir_station       ON fir(station_id);
CREATE INDEX idx_fir_crime_type    ON fir(crime_type_id);
CREATE INDEX idx_fir_status        ON fir(status);
```

### 3.2 Synthetic data generator

Create `db/seed.py`. Requirements:

- **Deterministic.** Seed with `random.seed(26072026)`. The demo must be reproducible.
- **~40 stations** across ~8 divisions in 3 districts. Include **Kengeri**, **Bengaluru South**, **Bengaluru City**, plus plausible others. Real station names, synthetic records.
- **~6,000 FIRs** spanning **Jan 2024 → Jul 2026**. Enough for quarter-over-quarter comparisons to be meaningful.
- **Deliberate signal to find.** Bake in the answers to the demo questions:
  - A visible cluster of chain-snatching near Kengeri in the trailing 6 months.
  - A burglary uptick in 2–3 specific stations this quarter vs last — so Q3 has a real answer.
  - FIR `0142/2026` at Kengeri station must exist, be a vehicle theft, and have a named IO.
- **Realistic messiness — this matters.** Include, at low rates:
  - ~3% NULL `occurred_on`
  - ~2% NULL lat/long
  - Mixed-case and whitespace-padded station names in a few rows
  - A handful of FIRs with `status='open'` and `registered_on` over 18 months ago

  Messiness is what makes the refusal path *demonstrable*. Do not generate a clean toy dataset.
- Write a `db/README.md` stating plainly: **all data synthetic, generated by seed.py, no real KSP records used.** Judges will ask. Have the answer in the repo.

---

## 4. The query template registry — the core of the build

This is the part that wins or loses the demo. Read carefully.

The LLM never writes SQL. It picks a `template_id` and returns slot values as JSON. Python validates the slots, then executes a hand-written parameterised query.

Create `app/templates/registry.py`. Each template is:

```python
@dataclass(frozen=True)
class QueryTemplate:
    template_id: str
    description: str          # shown to the LLM in the router prompt
    required_slots: tuple[str, ...]
    optional_slots: tuple[str, ...]
    sql: str                  # %(named)s placeholders only
    result_kind: Literal["rows", "scalar", "comparison"]
```

### Templates to implement (all six)

| id | Answers | Required slots | Optional |
|---|---|---|---|
| `T1_cases_by_type_area_period` | "chain-snatching near Kengeri, last 6 months" | `crime_type`, `period_start`, `period_end` | `station`, `division`, `district`, `radius_km` + `lat`/`lon` |
| `T2_count_by_status` | "how many vehicle thefts still open in Bengaluru South" | `status` | `crime_type`, `division`, `district`, `period_start`, `period_end` |
| `T3_period_over_period_by_station` | "biggest burglary increase this quarter vs last" | `crime_type`, `period_a_start`, `period_a_end`, `period_b_start`, `period_b_end` | `division`, `district`, `limit` |
| `T4_fir_lookup` | "who was the IO on FIR 0142/2026 at Kengeri" | `fir_number` | `station` |
| `T5_station_summary` | "what's the caseload at Kengeri station" | `station` | `period_start`, `period_end` |
| `T6_top_crime_types` | "most common crimes in Bengaluru South last month" | `period_start`, `period_end` | `division`, `district`, `station`, `limit` |

**If a question maps to none of these, the system refuses.** That is correct behaviour, not a gap. Say so on stage.

### Slot validation (`app/templates/validate.py`)

Pure Python, runs before any SQL touches the DB:

- `crime_type` → must fuzzy-match a row in `crime_type.label` (use `rapidfuzz`, threshold 80). No match → refusal with the near-misses offered as suggestions.
- `station` / `division` / `district` → must resolve against the hierarchy. Ambiguous match ("South" → 2 divisions) → **clarifying question**, not a guess.
- Dates → all relative expressions ("last six months", "this quarter") resolved in Python against a **fixed `NOW = 2026-07-22`** constant, not `datetime.now()`. Demo reproducibility. Put it in `app/config.py` as `DEMO_NOW`.
- `period_start < period_end`, and neither before `2024-01-01` (data floor) → else refuse and state the data range.
- `status` → must be one of the CHECK constraint values.
- `limit` → clamp to 50.

Every validation failure returns a structured `Refusal(reason, suggestion)`, never an exception to the user.

### Example template

```python
T1 = QueryTemplate(
    template_id="T1_cases_by_type_area_period",
    description=(
        "Retrieve individual FIR records filtered by crime type, geographic area, "
        "and a date range. Use when the user wants to SEE cases, not count them."
    ),
    required_slots=("crime_type", "period_start", "period_end"),
    optional_slots=("station", "division", "district", "lat", "lon", "radius_km"),
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
          AND (%(station)s  IS NULL OR s.name  = %(station)s)
          AND (%(division)s IS NULL OR dv.name = %(division)s)
          AND (%(district)s IS NULL OR dt.name = %(district)s)
        ORDER BY f.registered_on DESC
        LIMIT %(limit)s
    """,
    result_kind="rows",
)
```

Write T2–T6 in the same shape. T3 needs two CTEs and a `FULL OUTER JOIN` on station so stations appearing in only one period still surface — handle the NULL side explicitly.

---

## 5. LLM integration

### 5.1 Router call (`app/llm/router.py`)

**System prompt requirements:**
- Enumerate all six templates with `description` and slot lists.
- Instruct: respond with **JSON only**, no prose, no markdown fences.
- Provide `{"template_id": null, "reason": "..."}` as the mandated output when nothing fits. Make clear this is a *valid, expected* response, not a failure.
- Include `DEMO_NOW` in the prompt so relative dates are interpretable, but instruct the model to return relative expressions *verbatim* (`"last six months"`) — Python resolves them, not the LLM.

Output schema:
```json
{
  "template_id": "T1_cases_by_type_area_period",
  "slots": {"crime_type": "chain snatching", "period": "last six months", "station": "Kengeri"},
  "confidence": "high"
}
```

Parse defensively: strip fences, `json.loads`, validate against a pydantic model. On parse failure, retry once with a terser prompt, then refuse.

### 5.2 Synthesis call (`app/llm/synthesize.py`)

Input: the user's question + the **actual rows returned**, serialised compactly.

**System prompt requirements:**
- "Answer using ONLY the rows provided. Every factual claim must reference a `fir_number` or a count present in the data."
- "If the rows do not contain enough to answer, say so plainly."
- "Do not speculate about motive, likelihood, guilt, or the future."
- Cap at 4 sentences.

### 5.3 Grounding check (`app/llm/verify.py`) — pure Python, no LLM

After synthesis, before returning:
- Regex every `\d{4}/\d{4}` FIR-number-shaped token out of the answer. Any token not present in the result set → **strip the sentence containing it** and append a note that part of the response was suppressed.
- Regex bare integers claimed as counts; verify against `len(rows)` or the scalar result.
- Log every suppression to `logs/grounding.jsonl`.

This check firing on stage is a *feature*. If a judge asks "how do you know it isn't making things up," you open the log.

---

## 6. Kannada support

Cheapest real differentiator in the build. Input layer only.

- Detect script: if the string contains characters in the Kannada Unicode block (`ಀ-೿`), flag `lang="kn"`.
- Translate query → English with a single LLM call before routing.
- Route and execute in English.
- Translate the **final synthesised answer** back to Kannada; return **both** in the response payload so the UI can show English underneath. Judges who read Kannada will check it.
- Do **not** translate FIR numbers, station names, or officer names. Pass through verbatim.

Keep station-name transliterations in a small hand-written dict (`app/i18n/stations_kn.py`) — ಕೆಂಗೇರಿ → Kengeri, etc. LLM transliteration of proper nouns is unreliable and this list is 40 entries.

---

## 7. API

```
POST /api/query
  body:  {"text": str, "session_id": str}
  200:   {
           "answer": str,
           "answer_kn": str | null,
           "template_id": str | null,
           "resolved_slots": {...},
           "rows": [...],
           "citations": ["0142/2026", ...],
           "refused": bool,
           "refusal_reason": str | null,
           "sql_executed": str,          // shown in UI debug drawer
           "timing_ms": {"route": int, "sql": int, "synth": int}
         }

GET /api/health
GET /api/schema        // returns table+column list, for the UI's "what can I ask?" panel
```

`sql_executed` in the response is deliberate. Showing the exact parameterised query that ran is the strongest possible answer to "is this thing hallucinating?"

---

## 8. Frontend

Single page, three regions:

1. **Chat column (left, 60%)** — messages, input box, Kannada toggle. Refusals render in a visually distinct card (amber border), never as an error state. A refusal is a correct answer.
2. **Result panel (right, 40%)** — table of returned rows; each row's FIR number is clickable and highlights the corresponding citation in the answer text.
3. **Debug drawer (collapsed, bottom)** — `template_id`, resolved slots, the executed SQL, timings, and any grounding suppressions. **Open this during the demo.** It is the trust argument.

Seed the input with the five demo questions as clickable chips. Under pressure on stage, nobody wants to type Kannada.

Visual direction: dense, functional, government-tool-adjacent. Not a consumer chatbot. Neutral greys, one accent, tabular numerals, no rounded-pill aesthetic. It should look like something an officer would be issued, not something launched on Product Hunt.

---

## 9. Build order (four days)

Do not deviate. Each day ends with something demonstrable.

**Day 1 — data + templates**
Schema, seed generator, all six templates with hand-written SQL, slot validation. Verify every template by calling it directly from a Python REPL with hardcoded slots. No LLM yet, no UI. **Gate: all five demo questions answerable by manually calling templates.**

**Day 2 — LLM layer**
Router, synthesis, grounding check, `/api/query`. Test with the five demo questions plus at least ten questions that *should* refuse. **Gate: refusal rate on out-of-scope questions is 100%, hallucinated citations 0.**

**Day 3 — frontend + Kannada**
UI, debug drawer, Kannada path. **Gate: full loop working in browser for all five.**

**Day 4 — deploy + harden + rehearse**
Catalyst deployment (`KSPH26`), README, architecture diagram, demo script. Freeze code by evening. **Gate: deployed URL works from a phone on mobile data.**

If Day 3 slips, cut Kannada before cutting the debug drawer. The drawer is the differentiator; Kannada is the garnish.

---

## 10. Role split

- **Banit** — data layer + template registry + slot validation (§3, §4). The hardest and most load-bearing part; it's the SQL-heavy piece.
- **Rayan** — LLM integration + grounding check (§5).
- **Andrea** — frontend + debug drawer (§8).
- **Biyon (lead)** — Catalyst deployment, README, architecture diagram, PPT, demo script, and owning the five-question rehearsal.

Integration point is the `/api/query` contract in §7. Freeze that contract on Day 1 so three people can work in parallel against it.

---

## 11. Repo layout

```
ksp-copilot/
├── CLAUDE.md
├── README.md
├── docker-compose.yml          # postgres + api, for local dev
├── db/
│   ├── schema.sql
│   ├── seed.py
│   └── README.md               # "all data synthetic" statement
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # DEMO_NOW, model name, connection string
│   ├── db.py                   # psycopg pool
│   ├── templates/
│   │   ├── registry.py
│   │   └── validate.py
│   ├── llm/
│   │   ├── router.py
│   │   ├── synthesize.py
│   │   ├── verify.py
│   │   └── client.py           # thin httpx wrapper
│   └── i18n/
│       ├── detect.py
│       └── stations_kn.py
├── tests/
│   ├── test_templates.py       # each template, hardcoded slots
│   ├── test_validate.py        # every refusal path
│   └── test_grounding.py       # planted hallucinations must be stripped
└── web/
    └── src/...
```

---

## 12. README requirements

The README is a scored artifact. It must contain, in this order:

1. One-paragraph problem statement in KSP's language, not ML language.
2. **Synthetic data disclaimer, above the fold.**
3. Architecture diagram (the §2 ASCII block is acceptable; a rendered one is better).
4. **"Why we do not generate SQL with an LLM"** — a short, confident section. This is your strongest technical differentiator; state it plainly.
5. The refusal design, with a worked example.
6. Setup: `docker compose up`, seed, run. Must work from a clean clone.
7. Known limitations — written honestly. Six templates, synthetic data, no auth, Kannada is input/output translation not native understanding. Judges trust teams that name their own gaps.

---

## 13. What to say when a judge pushes

Rehearse these. They are asked every time.

- *"Can it handle any question?"* → No. Six query shapes, and it refuses outside them. Demonstrate a refusal live.
- *"Does it hallucinate?"* → Open the debug drawer. Show the executed SQL and the grounding log.
- *"Is this real police data?"* → No. Fully synthetic, generated by a seeded script in the repo, and here is the disclaimer.
- *"Why not just text-to-SQL?"* → Because arbitrary generated SQL against a live police database is an injection and correctness risk we are not willing to ship. Templates are auditable.
- *"What would you build next?"* → Template coverage expansion driven by real officer query logs, and a review queue where an analyst promotes a common refused question into a new template.

---

## 14. Out of scope — do not build

Authentication. Role-based access. Real-time ingestion. Predictive policing. Face recognition. Individual risk scoring. Mobile app. Multi-turn conversational memory beyond the last turn. Chart generation. PDF export.

Any of these will consume a day and win nothing.

---

## 15. Current state & onboarding (updated 2026-07-25)

Repo is **public**: https://github.com/banitsriram/ksp-copilot — anyone can read/fork; push access is by collaborator invite (Biyon, Andrea, Rayan).

**Secrets live outside git.** `.env`, `app-config.json` and `.catalystrc` are `.gitignore`d and have never been committed — verified across full history. They are shared privately (team chat), never in the repo:
- `GEMINI_API_KEY` — the build uses **Google Gemini** (`gemini-2.5-flash`), not the Anthropic API named in §5. Router/synthesis prompts are unchanged; only the client differs. Do **not** set `ANTHROPIC_API_KEY` in the deployed environment: `app/llm/client.py` checks Anthropic first and would route every query to a provider we do not use.
- `DATABASE_URL` — points at a **Neon** serverless Postgres (the demo DB, seeded from `db/seed.py`). Local dev can use the docker-compose Postgres instead. Note seeding is row-by-row with `autocommit=True`, so over a long-haul connection it takes ~30 minutes.

Rotate both credentials before the finale, and keep the deployed URL out of this repo and
off any public surface — the app has no authentication by design (§14).

**Local setup from a fresh clone:**
```
docker compose up                              # postgres + api
docker compose exec api python db/seed.py      # deterministic synthetic data (~5.9k FIRs)
# create .env + app-config.json from the values shared privately
```
Without Docker: create a venv on **Python 3.11 or 3.13** (the pinned dependencies have no
3.14 wheels), `pip install -r requirements.txt`, then export `DATABASE_URL` and
`GEMINI_API_KEY` **into the shell** — `app/config.py` reads `os.environ` directly and
nothing loads `.env` outside docker-compose — and run `uvicorn app.main:app --reload`.

**Deployment status: deployed and verified on Zoho Catalyst AppSail.** Verified against the
deployed URL, not locally: `/api/health` → `{"status":"ok","db":"up"}`; the UI is served by
the same AppSail service (no separate hosting needed for `web/`); all five §1 demo questions
answer correctly; the Q5 follow-up refuses; `pytest -q` passes. Answers were cross-checked
against direct SQL rather than trusting the app.

**Read `DEPLOY.md` before deploying.** Three non-obvious things break it, and all three
surface as the *same* opaque `503 Execution failed. Please check the startup command or
port.` while the CLI still reports "DEPLOYMENT SUCCESSFUL". The real error appears **only**
in the Catalyst console under **DevOps → Logs** — start there, not in CLI output:
1. `catalyst login --dc in` — without the flag, login succeeds but `project:list` is empty.
2. The runtime has **no `python` binary**; the start command must use `python3`.
3. Catalyst runs **no build step**, so `requirements.txt` is never installed. Dependencies
   are vendored as linux `cp311` wheels in `vendor/`, which is gitignored and **must be
   regenerated before deploying from a clean clone** (command in `DEPLOY.md`).

The connection pool in `app/db.py` opening at import time looks like a startup-failure
culprit and is **not** one. Do not "fix" it.

An ngrok static-domain tunnel over the local app remains the standby demo URL (`DEPLOY.md`
Path B).
