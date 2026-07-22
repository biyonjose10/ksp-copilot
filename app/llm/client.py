"""Thin httpx wrapper over the Anthropic Messages API. No framework indirection."""
from __future__ import annotations

import httpx

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_URL


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn completion. Returns the concatenated text of the response."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    resp = httpx.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    blocks = resp.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
