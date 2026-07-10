from __future__ import annotations

from app.summarizer import (
    TRUNCATION_MARK,
    fit_to_budget,
    llama_available,
    strip_thinking,
)


def test_fit_to_budget_keeps_short_text_untouched() -> None:
    assert fit_to_budget("short text", len, budget=100) == "short text"


def test_fit_to_budget_trims_the_middle() -> None:
    text = "A" * 1000 + "B" * 1000
    trimmed = fit_to_budget(text, len, budget=300)
    assert len(trimmed) <= 300
    assert TRUNCATION_MARK in trimmed
    # The head (agenda) and the tail (conclusions) both survive.
    assert trimmed.startswith("A")
    assert trimmed.endswith("B")


def test_fit_to_budget_uses_the_provided_tokenizer() -> None:
    # A "tokenizer" that counts words, not characters.
    def words(text: str) -> int:
        return len(text.split())

    text = " ".join(f"w{i}" for i in range(1000))
    trimmed = fit_to_budget(text, words, budget=50)
    assert words(trimmed) <= 50


def test_strip_thinking_removes_reasoning_blocks() -> None:
    raw = "<think>step 1... step 2...</think>\nThe summary.\n- point"
    assert strip_thinking(raw) == "The summary.\n- point"
    assert strip_thinking("plain output") == "plain output"


def test_llama_available_reports_a_boolean() -> None:
    assert isinstance(llama_available(), bool)
