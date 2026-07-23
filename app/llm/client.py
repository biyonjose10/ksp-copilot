"""Thin httpx wrapper over the LLM API. No framework indirection.

Anthropic Messages API when ANTHROPIC_API_KEY is set; falls back to the
Gemini REST API (free tier) when only GEMINI_API_KEY is available.
"""
from __future__ import annotations

import httpx

from app.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_URL,
    GEMINI_API_KEY, GEMINI_MODEL,
)


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn completion. Returns the concatenated text of the response."""
    if ANTHROPIC_API_KEY:
        return _anthropic(system, user, max_tokens)
    if GEMINI_API_KEY:
        return _gemini(system, user, max_tokens)
    raise RuntimeError("ANTHROPIC_API_KEY is not set")


def _anthropic(system: str, user: str, max_tokens: int) -> str:
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


def _gemini(system: str, user: str, max_tokens: int) -> str:
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        params={"key": GEMINI_API_KEY},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            # thinkingBudget 0: 2.5-flash otherwise spends the token budget on
            # internal reasoning and truncates the visible output.
            "generationConfig": {"maxOutputTokens": max_tokens,
                                 "thinkingConfig": {"thinkingBudget": 0}},
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    parts = resp.json()["candidates"][0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()
