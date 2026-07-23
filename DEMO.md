# Demo script — KSP Copilot

Five questions, in order. **Open the debug drawer before you start and leave it open.**
The drawer is the trust argument; the answers are secondary to *showing the work*.

Setup on the demo machine:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build      # wait for "Application startup complete"
open http://localhost:8000
```
Confirm `GET /api/health` returns `{"status":"ok"}` before you present.

---

### 0. Framing (15 seconds, before touching the keyboard)

> "This is a natural-language query layer over the KSP crime database. Two things make it
> trustworthy: it never lets the model write SQL — it fills hand-written templates — and
> every answer shows the exact query that ran and is checked against the data before you
> see it. All data here is synthetic. Let me show you."

---

### 1. Cases by type + area + period  → `T1`

Click the chip: **"Show me chain-snatching cases near Kengeri in the last six months."**

- Point at the **result table** filling with Kengeri chain-snatching FIRs.
- Point at the **debug drawer**: `template_id = T1_...`, resolved slots (note `period_start`
  became a real date), and the **executed SQL**.
- Line to say: *"That SQL is in our repo. The model chose the template and the filters — it
  did not write a single character of SQL."*

### 2. Count by status  → `T2`

Chip: **"How many vehicle theft FIRs are still open in Bengaluru South division?"**

- A single number. Point out `resolved_slots.status = "open"` in the drawer.
- Line: *"'still open' mapped to a validated status value. An unknown status would be refused,
  not guessed."*

### 3. Period-over-period trend  → `T3`

Chip: **"Which stations saw the biggest increase in burglary this quarter compared to last?"**

- Table ranked by change; Whitefield / JP Nagar / Yelahanka on top.
- Line: *"Two date ranges, both resolved in Python against a fixed demo date so this is
  reproducible. A full outer join so a station in only one quarter still shows up."*

### 4. Kannada  → `T6` / `T2`

Click the Kannada chip: **"ಕೆಂಗೇರಿಯಲ್ಲಿ ಕಳೆದ ತಿಂಗಳು ಎಷ್ಟು ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ?"**

- Answer comes back with **Kannada on top, English underneath**.
- Line: *"Kannada in, Kannada out. Station names and FIR numbers are never translated — they
  pass through verbatim."*

### 5. FIR lookup, then the refusal  → `T4` → refuse

Chip: **"Who was the investigating officer on FIR 0142/2026 at Kengeri station?"**

- Named officer, cited FIR number. Click the FIR number in the answer → the row highlights.

**Then type the follow-up:** `Is he likely to solve it?`

- It comes back as an **amber refusal card**, not an error.
- **This is the scoring moment.** Line: *"The data cannot answer that — it would be a
  prediction about a person. So it refuses. That is the correct behaviour, and it is by
  design, not a limitation we hit by accident."*

---

### If a judge pushes (rehearsed answers)

| Question | Answer |
|---|---|
| "Can it answer anything?" | No — six query shapes, refuses outside them. *(show a refusal)* |
| "Does it hallucinate?" | *Open the drawer.* Executed SQL + grounding log. Show `logs/grounding.jsonl`. |
| "Is this real data?" | No — fully synthetic, seeded script in the repo, disclaimer in the README. |
| "Why not text-to-SQL?" | Generated SQL on a live police DB is an injection + correctness risk. Templates are auditable. |
| "What's next?" | Coverage expansion from real officer query logs; an analyst review queue that promotes common refused questions into new templates. |

### Recovery if something breaks live

- Every question returns a "temporary error" card → the LLM is unreachable; check `ANTHROPIC_API_KEY` is set in the shell running Compose.
- Empty results → re-seed: `docker compose restart api` (re-runs `db/seed.py`, deterministic).
- Fall back to the pre-run screenshots for questions 1–4; **never skip the question-5 refusal** — it is the point.
