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
