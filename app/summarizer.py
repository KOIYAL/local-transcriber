"""Transcript summarization with a local GGUF model via llama-cpp-python.

The model file comes from :mod:`app.llm_manager` (modelshelf). llama-cpp is
an optional dependency (``pip install 'local-transcriber[summary]'``);
without it the feature reports itself unavailable and the app runs as
before.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Callable

SYSTEM_PROMPT = (
    "You summarize transcripts. Reply in the same language as the "
    "transcript. Output a 2-4 sentence summary, then the key points as "
    "short bullet lines starting with '- '. No preamble."
)

# Leave room inside the context window for the prompt scaffold + response.
CONTEXT_TOKENS = 8192
RESPONSE_TOKENS = 700
PROMPT_BUDGET = CONTEXT_TOKENS - RESPONSE_TOKENS - 256

TRUNCATION_MARK = "\n[...]\n"

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Drop chain-of-thought blocks that some models (Qwen3, …) emit."""
    return _THINK_RE.sub("", text).strip()


def llama_available() -> bool:
    try:
        import llama_cpp  # noqa: F401

        return True
    except Exception:
        return False


def fit_to_budget(
    text: str,
    count_tokens: Callable[[str], int],
    budget: int = PROMPT_BUDGET,
) -> str:
    """Trim `text` until `count_tokens(text) <= budget`.

    Long recordings matter most at the start (agenda) and the end
    (conclusions), so trimming removes the middle: keep the head and the
    tail, joined by a truncation mark. Pure function; unit-tested.
    """
    if count_tokens(text) <= budget:
        return text
    head_share = 0.6
    lo, hi = 0, len(text)
    # Binary-search the largest kept-length that fits the budget.
    while lo < hi:
        keep = (lo + hi + 1) // 2
        head = text[: int(keep * head_share)]
        tail = text[len(text) - (keep - int(keep * head_share)) :]
        if count_tokens(head + TRUNCATION_MARK + tail) <= budget:
            lo = keep
        else:
            hi = keep - 1
    head = text[: int(lo * head_share)]
    tail = text[len(text) - (lo - int(lo * head_share)) :] if lo else ""
    return head + TRUNCATION_MARK + tail


class SummaryEngine:
    """Loads the GGUF model lazily and serializes inference calls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._model_path: Path | None = None

    def _load(self, model_path: Path):
        from llama_cpp import Llama

        if self._model is None or self._model_path != model_path:
            self._model = Llama(
                model_path=str(model_path),
                n_ctx=CONTEXT_TOKENS,
                n_gpu_layers=int(os.getenv("LT_SUMMARY_GPU_LAYERS", "0")),
                verbose=False,
            )
            self._model_path = model_path
        return self._model

    def summarize(self, text: str, model_path: Path) -> str:
        # One inference at a time: a llama context is not thread-safe and
        # summaries are memory-hungry anyway.
        with self._lock:
            model = self._load(model_path)

            def count_tokens(chunk: str) -> int:
                return len(model.tokenize(chunk.encode("utf-8"), add_bos=False))

            prompt_text = fit_to_budget(text, count_tokens)
            completion = model.create_chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_text},
                ],
                max_tokens=RESPONSE_TOKENS,
                temperature=0.3,
            )
            summary = completion["choices"][0]["message"]["content"] or ""
            return strip_thinking(summary)
