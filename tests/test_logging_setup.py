"""Diagnostics never serialize speech, prompts, summaries or uploaded filenames."""
import logging
from types import SimpleNamespace

import pytest

from app import logging_setup
from app.jobs import JobRecord
from test_jobs import make_settings, manager, media, wait_until


@pytest.fixture
def diagnostics(tmp_path, monkeypatch):
    logger = logging.getLogger("app")
    previous = logger.level, logger.propagate
    enabled = []
    monkeypatch.setattr(logging_setup, "_handler", None)
    monkeypatch.setattr(logging_setup, "_crash_file", None)
    monkeypatch.setattr(logging_setup.faulthandler, "enable", lambda **kw: enabled.append(kw))
    logging_setup.setup_logging(make_settings(tmp_path), "0.7.2")
    yield tmp_path / "logs", enabled
    logger.removeHandler(logging_setup._handler)
    logging_setup._handler.close()
    logging_setup._crash_file.close()
    logger.setLevel(previous[0])
    logger.propagate = previous[1]


def test_startup_rotation_and_crash_file(diagnostics, monkeypatch):
    directory, enabled = diagnostics
    handler = logging_setup._handler
    assert handler.maxBytes == 1024 * 1024
    assert handler.backupCount == 3
    assert handler.encoding == "utf-8"
    assert enabled == [{"file": logging_setup._crash_file, "all_threads": True}]
    assert not enabled[0]["file"].closed
    calls = []
    monkeypatch.setattr(logging_setup.faulthandler, "dump_traceback", lambda **kw: calls.append(kw))
    logging_setup.dump_stacks()
    assert calls == enabled
    logging_setup.setup_logging(make_settings(directory.parent), "ignored")
    content = (directory / "backend.log").read_text(encoding="utf-8")
    assert content.count("startup") == 1
    for item in ("version=0.7.2", "os=", "arch=", "python=", "cpus=", "memory_gib=", "device=cpu", "compute_type=int8"):
        assert item in content
    handler.maxBytes = 200
    for _ in range(20):
        logging.getLogger("app.test").info("rotation check %s", "x" * 100)
    assert (directory / "backend.log.3").exists()
    assert not (directory / "backend.log.4").exists()


def test_transcription_and_job_failure_logs_exclude_private_data(diagnostics, manager, tmp_path, monkeypatch):
    directory, _ = diagnostics
    private = ["PRIVATE_TRANSCRIPT", "PRIVATE_GLOSSARY", "PRIVATE_SUMMARY", "PRIVATE_UPLOAD.wav"]

    class Model:
        def transcribe(self, path, **options):
            return iter([SimpleNamespace(id=0, start=0, end=1, text=private[0])]), SimpleNamespace(duration=2)

    monkeypatch.setattr(manager.engine, "_get_model", lambda *a, **kw: (Model(), "cpu"))
    path = media(tmp_path, private[3])
    result = manager.engine.transcribe(path, {"model": "tiny", "initial_prompt": private[1]}, lambda *a: None)
    assert result["text"] == private[0]

    def fail(*args):
        raise RuntimeError(" ".join(private))

    manager.engine.transcribe = fail
    job = JobRecord(id="safe-id", original_filename=private[3], media_path=path,
                    options={"initial_prompt": private[1]}, summary=private[2])
    manager._jobs[job.id] = job
    manager._run(job.id)
    # Third-party messages must not reach the diagnostic handler.
    logging.getLogger("faster_whisper").info(private[0])
    content = (directory / "backend.log").read_text(encoding="utf-8")
    for value in private:
        assert value not in content
    for event in ("transcription_start", "transcription_first_segment", "transcription_end", "job_failed", "RuntimeError", "Traceback:", "in fail"):
        assert event in content


@pytest.mark.parametrize("failure,event", [(None, "diarization_end"), (RuntimeError, "diarization_failed"), (TimeoutError, "diarization_timeout")])
def test_diarization_events(diagnostics, manager, tmp_path, failure, event):
    directory, _ = diagnostics
    manager.engine.transcribe = lambda *a: {"text": "PRIVATE_TEXT", "segments": []}

    def separate(*args, **kwargs):
        if failure:
            raise failure("PRIVATE_TEXT")
        return []

    manager.diarizer = SimpleNamespace(diarize=separate)
    job = JobRecord(id="test-job", original_filename="PRIVATE_NAME.wav",
                    media_path=media(tmp_path), options={"diarize": True})
    manager._jobs[job.id] = job
    manager._run(job.id)
    content = (directory / "backend.log").read_text(encoding="utf-8")
    assert "diarization_start job=test-job" in content
    assert event in content
    assert "PRIVATE_" not in content


def test_model_load_and_cuda_fallback_metadata(diagnostics, tmp_path, monkeypatch):
    import sys
    from dataclasses import replace
    from app.transcriber import TranscriptionEngine

    directory, _ = diagnostics
    devices = []

    class Model:
        def __init__(self, source, **kwargs):
            devices.append(kwargs["device"])
            if kwargs["device"] == "cuda":
                raise RuntimeError("CUDA PRIVATE_ERROR")

        def transcribe(self, *args, **kwargs):
            return iter([]), SimpleNamespace(duration=1)

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    engine = TranscriptionEngine(replace(make_settings(tmp_path), device="auto"))
    monkeypatch.setattr(engine, "_runtime", lambda force_cpu: ("cpu", "int8") if force_cpu else ("cuda", "auto"))
    engine.transcribe(tmp_path / "PRIVATE_AUDIO.wav", {"model": "tiny"}, lambda *a: None)
    assert devices == ["cuda", "cpu"]
    content = (directory / "backend.log").read_text(encoding="utf-8")
    assert "model_load_start model=tiny device=cuda compute_type=auto" in content
    assert "model_load_end model=tiny device=cpu compute_type=int8 seconds=" in content
    assert "cuda_to_cpu model=tiny" in content
    assert "PRIVATE_" not in content
