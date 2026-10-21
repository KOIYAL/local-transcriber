from app.transcriber import TranscriptionEngine


def test_glossary_and_repetition_prevention_reach_whisper(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from app.config import SETTINGS

    captured = {}

    class FakeModel:
        def transcribe(self, path, **kwargs):
            captured.update(kwargs)
            return iter([]), SimpleNamespace(duration=1, language="ja")

    engine = TranscriptionEngine(SETTINGS)
    monkeypatch.setattr(engine, "_get_model", lambda *args, **kwargs: (FakeModel(), "cpu"))
    engine.transcribe(
        tmp_path / "fake.wav", {"model": "turbo", "initial_prompt": "KOIYAL"},
        lambda *args: None,
    )
    assert captured["initial_prompt"] == "KOIYAL"
    assert captured["condition_on_previous_text"] is False


def test_detects_cuda_runtime_errors() -> None:
    assert TranscriptionEngine._is_cuda_runtime_error(
        RuntimeError("Library cublas64_12.dll is not found")
    )
    assert TranscriptionEngine._is_cuda_runtime_error(
        RuntimeError("CUDA out of memory")
    )
    assert not TranscriptionEngine._is_cuda_runtime_error(
        RuntimeError("The media file is invalid")
    )


def test_unsupported_compute_type_triggers_cpu_fallback() -> None:
    # CTranslate2 raises ValueError (not RuntimeError) for a GPU without
    # efficient float16; the CPU retry must cover it.
    assert TranscriptionEngine._is_cuda_runtime_error(
        ValueError(
            "Requested float16 compute type, but the target device or backend "
            "do not support efficient float16 computation."
        )
    )
