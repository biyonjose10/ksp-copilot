# Database — synthetic data statement

**All data in this database is synthetic.** It is generated entirely by `db/seed.py`.
No real Karnataka State Police records, no real FIRs, no real names, and no scraped
data of any kind are used anywhere in this project.

- **Generator:** `db/seed.py`, seeded with `random.seed(26072026)` — fully reproducible.
- **Volume:** ~5,900 FIRs across 40 stations, 8 divisions, 3 districts, Jan 2024 → Jul 2026.
- **Names, summaries, coordinates:** invented. Any resemblance to real persons or cases is coincidental.

## Planted signals (so the demo questions have real answers)

- A cluster of **chain-snatching** FIRs near **Kengeri** in the trailing six months.
- A **burglary** uptick at Whitefield / JP Nagar / Yelahanka this quarter vs last.
- **FIR `0142/2026`** at Kengeri station — a vehicle theft with a named investigating officer.

## Deliberate messiness (so the refusal path is demonstrable)

- ~3% of FIRs have a NULL `occurred_on`.
- ~2% have NULL latitude/longitude.
- ~20 FIRs are still `open` while registered over 18 months ago.

## Regenerate

```bash
python db/seed.py     # requires DATABASE_URL, applies schema.sql then seeds
```
