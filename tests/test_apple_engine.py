"""AppleIntelligenceEngine drives a Swift helper; these tests fake it."""

from __future__ import annotations

import json

from app.apple_intelligence import (
    INSTRUCTIONS_CHUNK,
    INSTRUCTIONS_FINAL,
    AppleIntelligenceEngine,
    _split,
)


class FakeCompleted:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def make_runner(handler, calls: list):
    def run(argv: list[str], input=None, **_kwargs) -> FakeCompleted:
        payload = json.loads(input) if input else None
        calls.append((argv[1:], payload))
        return handler(argv[1:], payload)

    return run


def available_check(context_size: int = 4096):
    return FakeCompleted(
        stdout=json.dumps({"available": True, "context_size": context_size})
    )


def test_without_helper_the_engine_is_unavailable() -> None:
    engine = AppleIntelligenceEngine(helper=None)
    assert engine.available() is False
    assert engine.check()["reason"] == "helper_missing"


def test_availability_probe_is_cached() -> None:
    calls: list = []

    def handler(args, _payload):
        assert args == ["check"]
        return available_check()

    engine = AppleIntelligenceEngine(helper="helper-fake", runner=make_runner(handler, calls))
    assert engine.available() is True
    assert engine.available() is True
    assert len(calls) == 1, "the second probe must come from the cache"


def test_summarize_short_text_is_a_single_final_pass() -> None:
    calls: list = []

    def handler(args, payload):
        if args == ["check"]:
            return available_check()
        assert args == ["summarize"]
        assert payload["instructions"] == INSTRUCTIONS_FINAL
        return FakeCompleted(stdout=json.dumps({"summary": "  BULLETED SUMMARY  "}))

    engine = AppleIntelligenceEngine(helper="helper-fake", runner=make_runner(handler, calls))
    assert engine.summarize("短い議事録テキスト。") == "BULLETED SUMMARY"
    summarize_calls = [c for c in calls if c[0] == ["summarize"]]
    assert len(summarize_calls) == 1


def test_long_text_is_summarized_map_reduce_style() -> None:
    calls: list = []

    def handler(args, payload):
        if args == ["check"]:
            # Tiny context -> chunk budget of 1024 characters.
            return available_check(context_size=900)
        if payload["instructions"] == INSTRUCTIONS_CHUNK:
            return FakeCompleted(stdout=json.dumps({"summary": "- 部分要約"}))
        return FakeCompleted(stdout=json.dumps({"summary": "最終要約"}))

    engine = AppleIntelligenceEngine(helper="helper-fake", runner=make_runner(handler, calls))
    long_text = "これは長い会議の記録です。" * 250  # ~3250 chars
    assert engine.summarize(long_text) == "最終要約"

    instructions = [c[1]["instructions"] for c in calls if c[0] == ["summarize"]]
    assert instructions.count(INSTRUCTIONS_CHUNK) >= 2, "chunks must be summarized first"
    assert instructions[-1] == INSTRUCTIONS_FINAL, "…then one final pass"
    # Every chunk request honored the budget.
    for args, payload in calls:
        if args == ["summarize"]:
            assert len(payload["text"]) <= 1024


def test_context_overflow_splits_and_retries() -> None:
    calls: list = []
    state = {"overflowed": False}

    def handler(args, payload):
        if args == ["check"]:
            return available_check()
        if not state["overflowed"]:
            state["overflowed"] = True
            return FakeCompleted(
                stdout=json.dumps({"error": "context_overflow"}), returncode=1
            )
        return FakeCompleted(
            stdout=json.dumps({"summary": f"- {len(payload['text'])}字分"})
        )

    engine = AppleIntelligenceEngine(helper="helper-fake", runner=make_runner(handler, calls))
    result = engine.summarize("会議の記録。" * 60)  # single chunk, then overflow
    assert result.count("字分") == 2, "the overflowing text must be split in two"


def test_split_prefers_sentence_boundaries() -> None:
    text = ("一文目です。" * 30) + ("Second sentence here. " * 30)
    pieces = _split(text, 200)
    assert all(len(piece) <= 200 for piece in pieces)
    assert "".join(pieces).replace(" ", "") == text.replace(" ", "")
    # Most pieces should end at a sentence boundary.
    boundary_endings = sum(piece.endswith(("。", ".", "!", "?")) for piece in pieces)
    assert boundary_endings >= len(pieces) - 1
