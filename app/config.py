"""Central config. DEMO_NOW is fixed for reproducibility — never use datetime.now()."""
import os
import datetime as dt

# Fixed "current date" for the whole system. All relative dates resolve against this.
DEMO_NOW = dt.date(2026, 7, 22)

# Data floor — no FIRs exist before this (see db/seed.py).
DATA_FLOOR = dt.date(2024, 1, 1)

DB_URL = os.environ.get("DATABASE_URL", "postgresql://ksp:ksp@localhost:5432/ksp")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Fallback provider for the prototype when no Anthropic key is available.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
