"""Apple Intelligence summary engine (macOS).

Uses the on-device Apple Intelligence foundation model through a tiny
bundled Swift helper (``desktop/apple-intelligence-helper``) speaking JSON
over stdin/stdout — the FoundationModels framework is Swift-only, so the
Python backend cannot call it directly.

Preferred over the local-LLM engine when available (see ``app.main``):
no model download, no extra disk or memory, and summarization is exactly
what the system model is tuned for. The model's context window is small
(~4096 shared tokens), so long transcripts are summarized map-reduce
style: chunk summaries first, then a final pass over those.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

HELPER_ENV = "LT_APPLE_AI_HELPER"
HELPER_NAME = "apple-intelligence-helper"

CHECK_TIMEOUT = 20
SUMMARIZE_TIMEOUT = 10 * 60

# The availability probe spawns a process; cache it briefly (the user may
# enable Apple Intelligence in System Settings while the app runs).
CHECK_CACHE_SECONDS = 60.0

INSTRUCTIONS_FINAL = (
    "You summarize transcripts. Reply in the same language as the "
    "transcript. Output a 2-4 sentence summary, then the key points as "
    "short bullet lines starting with '- '. No preamble."
)
INSTRUCTIONS_CHUNK = (
    "You summarize one part of a longer transcript. Reply in the same "
    "language as the transcript. Output only the essential facts and "
    "decisions of this part as short bullet lines starting with '- '. "
    "No preamble."
)

# Conservative sizing against the shared ~4096-token window: leave room
# for instructions and the response, and assume ~2 characters per token
# (safe for Japanese; English is far less dense).
DEFAULT_CONTEXT_TOKENS = 4096
RESPONSE_TOKENS = 600
CHARS_PER_TOKEN = 2.0

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

_UNSET: Any = object()


def _default_helper() -> str | None:
    override = os.getenv(HELPER_ENV, "").strip()
    if override:
        return override if Path(override).exists() else None
    if sys.platform != "darwin":
        return None
    # Packaged desktop builds ship the helper with the backend
    # (desktop/backend.spec), like the modelshelf CLI.
    from app.llm_manager import _bundled_candidates

    for bundled in _bundled_candidates(HELPER_NAME):
        if bundled.exists():
            return str(bundled)
    return shutil.which(HELPER_NAME)


class AppleIntelligenceEngine:
    """Availability probe + chunked summarization over the Swift helper."""

    def __init__(
        self,
        helper: str | None = _UNSET,
        runner: Runner = subprocess.run,
    ) -> None:
        self.helper = _default_helper() if helper is _UNSET else helper
        self._runner = runner
        self._lock = threading.Lock()
        self._checked_at = 0.0
        self._check: dict[str, Any] = {"available": False}

    # -- helper protocol -----------------------------------------------------

    def _run(self, *args: str, payload: dict | None = None, timeout: int) -> dict:
        assert self.helper is not None
        completed = self._runner(
            [self.helper, *args],
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        text = (completed.stdout or "").strip()
        try:
            result = json.loads(text) if text else {}
        except ValueError:
            result = {}
        if completed.returncode != 0 and "error" not in result:
            stderr = (completed.stderr or "").strip().splitlines()
            result["error"] = stderr[-1] if stderr else f"exit code {completed.returncode}"
        return result

    def check(self) -> dict[str, Any]:
        """Cached availability probe: `{available, context_size?, reason?}`."""
        if self.helper is None:
            return {"available": False, "reason": "helper_missing"}
        now = time.monotonic()
        if now - self._checked_at < CHECK_CACHE_SECONDS:
            return self._check
        try:
            result = self._run("check", timeout=CHECK_TIMEOUT)
        except Exception as exc:
            result = {"available": False, "reason": str(exc)}
        self._check = {"available": bool(result.get("available")), **result}
        self._checked_at = now
        return self._check

    def available(self) -> bool:
        return self.check()["available"]

    # -- summarization -------------------------------------------------------

    def summarize(self, text: str) -> str:
        with self._lock:
            context = int(self.check().get("context_size") or DEFAULT_CONTEXT_TOKENS)
            budget_tokens = max(context - RESPONSE_TOKENS - 256, 512)
            chunk_chars = int(budget_tokens * CHARS_PER_TOKEN)

            chunks = _split(text, chunk_chars)
            if len(chunks) == 1:
                return self._summarize_once(chunks[0], INSTRUCTIONS_FINAL, chunk_chars)

            partials = [
                self._summarize_once(chunk, INSTRUCTIONS_CHUNK, chunk_chars)
                for chunk in chunks
            ]
            combined = "\n".join(partials)
            # Reduce until the combined notes fit a final pass.
            while len(combined) > chunk_chars:
                partials = [
                    self._summarize_once(part, INSTRUCTIONS_CHUNK, chunk_chars)
                    for part in _split(combined, chunk_chars)
                ]
                combined = "\n".join(partials)
            return self._summarize_once(combined, INSTRUCTIONS_FINAL, chunk_chars)

    def _summarize_once(self, text: str, instructions: str, chunk_chars: int) -> str:
        result = self._run(
            "summarize",
            payload={"instructions": instructions, "text": text},
            timeout=SUMMARIZE_TIMEOUT,
        )
        if result.get("error") == "context_overflow" and len(text) > 200:
            # Our chars-per-token estimate was too optimistic for this
            # text: split and merge the halves.
            halves = _split(text, max(len(text) // 2, 100))
            return "\n".join(
                self._summarize_once(half, instructions, chunk_chars)
                for half in halves
            )
        if "error" in result:
            raise RuntimeError(f"Apple Intelligence helper failed: {result['error']}")
        return str(result.get("summary", "")).strip()


def _split(text: str, chunk_chars: int) -> list[str]:
    """Split on sentence-ish boundaries into pieces of <= chunk_chars."""
    if len(text) <= chunk_chars:
        return [text]
    pieces: list[str] = []
    remaining = text
    while len(remaining) > chunk_chars:
        window = remaining[:chunk_chars]
        cut = max(
            window.rfind("\n"),
            window.rfind("。"),
            window.rfind(". "),
            window.rfind("! "),
            window.rfind("? "),
        )
        if cut < chunk_chars // 2:
            cut = chunk_chars - 1
        pieces.append(remaining[: cut + 1].strip())
        remaining = remaining[cut + 1 :]
    if remaining.strip():
        pieces.append(remaining.strip())
    return [piece for piece in pieces if piece]
