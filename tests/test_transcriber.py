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
    assert captured["hotwords"] == "KOIYAL"
    assert captured.get("initial_prompt") is None
    assert captured["condition_on_previous_text"] is False


def test_glossary_reaches_every_window_in_whisper_loop(monkeypatch, tmp_path):
    import logging
    from types import SimpleNamespace

    import numpy as np
    from faster_whisper import WhisperModel
    from app.config import SETTINGS

    prompts = []
    glossary_token, speech_token = 42, 43
    tokenizer = SimpleNamespace(
        sot_prev=1, sot_sequence=[2, 3], timestamp_begin=100,
        encode=lambda text: [glossary_token] if text.strip() == "KOIYAL" else [],
        decode=lambda tokens: "hello",
    )

    # Exercise the installed library's real window/reset/prompt logic, replacing
    # only audio features, tokenization and native model inference.
    class FakeModel(WhisperModel):
        def __init__(self):
            self.feature_extractor = SimpleNamespace(time_per_frame=0.01, nb_max_frames=3000)
            self.frames_per_second = 100
            self.time_precision = 0.02
            self.max_length = 448
            self.logger = logging.getLogger("fake-whisper")

        def transcribe(self, path, **kwargs):
            options = SimpleNamespace(
                initial_prompt=kwargs.get("initial_prompt"), hotwords=kwargs.get("hotwords"),
                condition_on_previous_text=kwargs["condition_on_previous_text"],
                clip_timestamps="0", multilingual=False, without_timestamps=False,
                prefix=None, no_speech_threshold=None, word_timestamps=False,
            )
            return self.generate_segments(np.zeros((80, 9001)), tokenizer, options, False), \
                SimpleNamespace(duration=90, language="ja")

        def encode(self, features):
            return None

        def generate_with_fallback(self, encoded, prompt, tokenizer, options):
            prompts.append(prompt)
            return SimpleNamespace(sequences_ids=[[speech_token]], no_speech_prob=0), 0, 0, 1

    engine = TranscriptionEngine(SETTINGS)
    monkeypatch.setattr(engine, "_get_model", lambda *args, **kwargs: (FakeModel(), "cpu"))
    result = engine.transcribe(tmp_path / "fake.wav",
                              {"model": "tiny", "initial_prompt": "KOIYAL"}, lambda *args: None)
    assert [segment["start"] for segment in result["segments"]] == [0, 30, 60]
    assert len(prompts) == 3
    assert all(prompt.count(glossary_token) == 1 for prompt in prompts)
    assert all(speech_token not in prompt for prompt in prompts)


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
