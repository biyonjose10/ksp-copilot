# Deployment

Two paths. **Path B (any Docker host) is proven working today** and is the safe fallback for
the prototype deadline. **Path A (Zoho Catalyst)** is the sponsor-aligned target for the
finale — use the promo code **`KSPH26`**.

> ⚠️ **Postgres note that decides everything.** Catalyst's built-in data store is **not**
> vanilla PostgreSQL, and our templates rely on Postgres SQL (CTEs, `FULL OUTER JOIN`,
> window-style aggregation). So on Catalyst the app must talk to an **external managed
> Postgres** via `DATABASE_URL` (Neon / Supabase / RDS free tier all work — data is
> synthetic and seeded on boot, so an ephemeral instance is fine). Do not try to port the
> schema to Catalyst's data store.

---

## Path A — Zoho Catalyst AppSail (managed Python runtime)

Reference: <https://docs.catalyst.zoho.com/en/cli/v1/add-appsail/> ·
<https://docs.catalyst.zoho.com/en/serverless/help/appsail/help-guides/python/overview/>

### 1. Provision an external Postgres and seed it
```bash
export DATABASE_URL='postgresql://user:pass@your-managed-pg-host:5432/ksp?sslmode=require'
python db/seed.py            # one-time; deterministic, re-runnable
```

### 2. Install + log in to the Catalyst CLI
```bash
npm install -g zcatalyst-cli
catalyst login
catalyst init                # create/select the project, apply promo code KSPH26 in the console
```

### 3. Add the AppSail service
```bash
catalyst appsail:add
# prompts:
#   Runtime Type   -> Catalyst-Managed Runtime
#   Sample project -> N (use our own app)
#   Source dir     -> . (repo root)
#   App name       -> ksp-copilot
#   Stack/runtime  -> Python (3.11 if offered; else newest available)
```
This writes **`app-config.json`** in the source dir. Edit it to set the startup command,
env vars, and memory:

```jsonc
{
  "name": "ksp-copilot",
  "stack": "python3",
  // AppSail injects the port to bind as an env var — bind to it, don't hardcode 8000.
  "command": "uvicorn app.main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}",
  "memory": 512,
  "env_variables": {
    "DATABASE_URL": "postgresql://user:pass@your-managed-pg-host:5432/ksp?sslmode=require",
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "ANTHROPIC_MODEL": "claude-sonnet-5"
  }
}
```
`requirements.txt` at the repo root is installed automatically by the Python buildpack.

> `# TODO(team):` confirm two field names against the current console when you deploy —
> (1) the exact listen-port env var (shown as `X_ZOHO_CATALYST_LISTEN_PORT` in Catalyst
> examples), and (2) the `stack`/`command` key names AppSail wrote into your generated
> `app-config.json`. The CLI-generated file is the source of truth; edit its values, don't
> invent new keys.

### 4. Deploy
```bash
catalyst deploy              # deploys AppSail + any other resources
```
Catalyst prints the hosted URL. Open it, confirm `GET /api/health` → `{"status":"ok"}`.

### Alternative: custom Docker runtime on AppSail
AppSail also supports a custom Docker runtime — our `Dockerfile` works, but drop the
`python db/seed.py &&` from its `CMD` (seed the external PG once from your laptop instead of
on every cold start) and bind uvicorn to the injected port. See
<https://docs.catalyst.zoho.com/en/serverless/help/appsail/custom-runtimes/deploy-from-cli/>.

---

## Path B — any Docker host (proven, the fallback)

Everything already runs under Compose. On any VM with Docker (or locally for the prototype
demo):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose up --build -d
# -> Postgres starts, db/seed.py runs, uvicorn serves app+UI on :8000
```
Put it behind a reverse proxy / tunnel (Caddy, nginx, or `cloudflared tunnel`) for a public
URL. This is the configuration verified working during the build.

---

## Pre-demo checklist

- [ ] `GET /api/health` returns `{"status":"ok","db":"up"}` on the deployed URL
- [ ] All five demo questions answer (see `DEMO.md`), and the question-5 refusal fires
- [ ] `ANTHROPIC_API_KEY` is set in the deployed env (without it every query returns a "temporary error" refusal card)
- [ ] Opens on a phone over mobile data (Day-4 gate)
- [ ] Debug drawer shows executed SQL — this is the trust argument, rehearse opening it

---

## Catalyst AppSail — gotchas found while deploying (2026-07-25)

Deployed and verified working. The deployed URL is deliberately **not** recorded in this
repo — the repo is public and the app has no authentication by design (CLAUDE.md §14).
Get it from team chat.

Three things the docs do not tell you, each of which fails as a bare
`503 Execution failed. Please check the startup command or port.`
The real error is only visible in **DevOps -> Logs**, not in the CLI output.

1. **`python` does not exist in the runtime — use `python3`.**
   `"command": "python server.py"` fails with
   `exec failed: python server.py : No such file or directory (os error 2)`.

2. **`requirements.txt` is NOT installed.** Deployments report Success with
   `Deployment Logs: N/A` — there is no build step at all, so the app dies on
   `ModuleNotFoundError: No module named 'uvicorn'`. Dependencies must be
   vendored as linux `cp311` wheels. From the repo root, on any OS:

   ```
   pip install "fastapi==0.115.6" "uvicorn==0.34.0" "psycopg[binary]==3.2.3" \
     "psycopg_pool==3.2.4" "httpx==0.28.1" "rapidfuzz==3.10.1" "pydantic==2.10.4" \
     --target vendor --platform manylinux2014_x86_64 --python-version 3.11 \
     --only-binary=:all: --implementation cp
   ```

   `server.py` prepends `vendor/` to `sys.path` before importing uvicorn.
   `vendor/` is gitignored — regenerate it before deploying from a clean clone.

3. **CLI login needs the India DC:** `catalyst login --dc in`. Without it the
   CLI authenticates but `project:list` comes back empty.

`app-config.json` (gitignored) carries `GEMINI_API_KEY`, `GEMINI_MODEL` and
`DATABASE_URL`. Note the app uses **Gemini**, so do not set `ANTHROPIC_API_KEY`
there — `app/llm/client.py` checks Anthropic first and would route to it.
