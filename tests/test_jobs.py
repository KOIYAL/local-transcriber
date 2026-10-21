"""JobManager: source-file lifecycle and the in-memory job bound."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.config import Settings
from app.jobs import MAX_JOBS, JobManager


def make_settings(tmp_path: Path, keep_uploads: bool = False) -> Settings:
    return Settings(
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        model_dir=tmp_path / "models",
        max_upload_bytes=1024,
        keep_uploads=keep_uploads,
        device="cpu",
        compute_type="int8",
        local_model=None,
        max_workers=1,
    )


def wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


@pytest.fixture()
def manager(tmp_path: Path) -> JobManager:
    settings = make_settings(tmp_path)
    settings.upload_dir.mkdir()
    m = JobManager(settings)
    yield m
    m.shutdown()


def media(tmp_path: Path, name: str = "meeting.webm") -> Path:
    path = tmp_path / "uploads" / name
    path.write_bytes(b"audio")
    return path


def test_source_is_deleted_only_after_success(manager: JobManager, tmp_path: Path) -> None:
    manager.engine.transcribe = lambda path, options, progress: {
        "text": "hi",
        "segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "hi"}],
        "language": "en",
        "language_probability": 1.0,
        "duration": 1.0,
        "model": "tiny",
        "device": "cpu",
        "task": "transcribe",
    }
    path = media(tmp_path)
    job = manager.submit("meeting.webm", path, {"model": "tiny"})
    wait_until(lambda: manager.get(job.id).status == "completed")
    assert not path.exists()
    assert (tmp_path / "outputs" / job.id / "transcript.txt").exists()


def test_source_is_kept_when_transcription_fails(manager: JobManager, tmp_path: Path) -> None:
    def boom(path, options, progress):
        raise RuntimeError("CUDA out of memory")

    manager.engine.transcribe = boom
    path = media(tmp_path)
    job = manager.submit("meeting.webm", path, {"model": "tiny"})
    wait_until(lambda: manager.get(job.id).status == "failed")
    assert path.exists(), "a failed in-app recording is the only copy; keep it"
    assert "CUDA" in manager.get(job.id).error
    # The user's explicit delete removes it.
    assert manager.delete(job.id)
    assert not path.exists()


def test_old_finished_jobs_are_forgotten_beyond_the_bound(
    manager: JobManager, tmp_path: Path
) -> None:
    manager.engine.transcribe = lambda path, options, progress: {
        "text": "x",
        "segments": [],
        "language": "en",
        "language_probability": 1.0,
        "duration": 1.0,
        "model": "tiny",
        "device": "cpu",
        "task": "transcribe",
    }
    first = manager.submit("a.webm", media(tmp_path, "a.webm"), {"model": "tiny"})
    wait_until(lambda: manager.get(first.id).status == "completed")
    for n in range(MAX_JOBS):
        job = manager.submit(f"j{n}.webm", media(tmp_path, f"j{n}.webm"), {"model": "tiny"})
        wait_until(lambda: manager.get(job.id) is None or manager.get(job.id).status == "completed")
    assert manager.get(first.id) is None, "the oldest finished job is pruned"
    assert len(manager.list_recent(limit=1000)) == MAX_JOBS


def test_list_payload_omits_transcript_text() -> None:
    from app.jobs import JobRecord

    job = JobRecord(
        id="j",
        original_filename="m.wav",
        media_path=Path("m.wav"),
        options={},
        status="completed",
        result={"text": "secret", "segments": [1, 2, 3]},
        summary="sum",
        summary_status="completed",
    )
    full = job.as_dict()
    assert full["result"]["text"] == "secret"
    assert full["summary"]["text"] == "sum"
    brief = job.as_dict(include_result=False)
    assert "result" not in brief
    assert brief["summary"] == {"status": "completed", "text": None, "error": None}


@pytest.mark.parametrize("enabled,fail", [(False, False), (True, False), (True, True)])
def test_optional_diarization_runs_before_exports_and_preserves_fallback(manager, tmp_path, enabled, fail):
    import json
    from types import SimpleNamespace

    calls = []
    manager.engine.transcribe = lambda *args: {
        "text": "hello world", "segments": [
            {"start": 0, "end": 1, "text": "hello"},
            {"start": 1, "end": 2, "text": "world"},
        ],
    }

    def separate(path, progress):
        calls.append(path)
        job = manager.list_recent()[0]
        assert job.status == "diarizing"
        assert not manager.delete(job.id)
        progress(0.5)
        assert job.progress == pytest.approx(0.915)
        if fail:
            raise RuntimeError("native inference failed")
        return [{"start": 0, "end": 1, "speaker": 9}, {"start": 1, "end": 2, "speaker": 4}]

    manager.diarizer = SimpleNamespace(diarize=separate)
    path = media(tmp_path)
    job = manager.submit("meeting.wav", path, {"model": "tiny", "diarize": enabled})
    wait_until(lambda: job.status == "completed")
    if fail:
        assert path.exists()
        assert job.result["diarization_failed"] is True
        assert job.result["text"] == "hello world"
    else:
        wait_until(lambda: not path.exists())
    if enabled and not fail:
        assert job.result["text"] == "話者1: hello\n話者2: world"
        payload = json.loads(job.exports["json"].read_text(encoding="utf-8"))
        assert payload["segments"][1]["speaker"] == "話者2"
        assert job.exports["txt"].read_text(encoding="utf-8") == "話者1: hello\n話者2: world\n"
    else:
        assert all("speaker" not in s for s in job.result["segments"])
    assert len(calls) == int(enabled)


@pytest.mark.parametrize("failure", ["exception", "crash", "timeout"])
def test_child_diarization_failure_keeps_transcript_and_source(manager, tmp_path, failure):
    from test_diarizer import (
        fake_manager, failing_process_worker, crashing_process_worker, hanging_process_worker,
    )

    worker = {"exception": failing_process_worker, "crash": crashing_process_worker,
              "timeout": hanging_process_worker}[failure]
    manager.diarizer, _ = fake_manager(tmp_path, worker=worker, timeout=2)
    manager.diarizer._provision()
    manager.engine.transcribe = lambda *args: {
        "text": "hello", "segments": [{"start": 0, "end": 1, "text": "hello"}],
    }
    path = media(tmp_path)
    job = manager.submit("meeting.wav", path, {"model": "tiny", "diarize": True})
    wait_until(lambda: job.status == "completed", timeout=10)
    assert job.result["diarization_failed"] is True
    assert job.result["text"] == "hello"
    assert "speaker" not in job.result["segments"][0]
    assert job.exports["txt"].read_text(encoding="utf-8") == "hello\n"
    assert path.exists()
