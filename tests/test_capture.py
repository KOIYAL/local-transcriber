from pathlib import Path

import pytest

from app.capture import RecordingError, RecordingManager, SILENCE_WARN_SECONDS


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class SubmitSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path, dict]] = []

    def __call__(self, filename: str, path: Path, options: dict) -> dict:
        self.calls.append((filename, path, options))
        return {"id": "job-1", "filename": filename}


@pytest.fixture()
def manager(tmp_path: Path) -> tuple[RecordingManager, SubmitSpy, FakeClock]:
    clock = FakeClock()
    spy = SubmitSpy()
    return (
        RecordingManager(tmp_path, spy, max_bytes=1024, clock=clock),
        spy,
        clock,
    )


def test_record_chunks_then_stop_submits_job(manager) -> None:
    mgr, spy, clock = manager
    status = mgr.start()
    sid = status["session_id"]
    assert status["state"] == "recording"
    assert status["filename"].startswith("recording-")
    assert status["filename"].endswith(".webm")

    mgr.append_chunk(sid, b"abc", level=0.5)
    clock.advance(2.0)
    status = mgr.append_chunk(sid, b"def", level=0.5)
    assert status["bytes_written"] == 6
    assert status["elapsed_seconds"] == pytest.approx(2.0)

    job = mgr.stop(sid, {"model": "tiny"})
    assert job["id"] == "job-1"
    assert len(spy.calls) == 1
    filename, path, options = spy.calls[0]
    assert path.read_bytes() == b"abcdef"
    assert options == {"model": "tiny"}
    assert mgr.status() == {"state": "idle"}


def test_second_start_conflicts(manager) -> None:
    mgr, _, _ = manager
    mgr.start()
    with pytest.raises(RecordingError) as excinfo:
        mgr.start()
    assert excinfo.value.code == "recording_in_progress"
    assert excinfo.value.http_status == 409


def test_unsupported_mime_rejected(manager) -> None:
    mgr, _, _ = manager
    with pytest.raises(RecordingError) as excinfo:
        mgr.start(mime="audio/x-unknown")
    assert excinfo.value.code == "unsupported_recording_mime"


def test_pause_stops_the_clock(manager) -> None:
    mgr, _, clock = manager
    sid = mgr.start()["session_id"]
    clock.advance(3.0)
    status = mgr.pause(sid)
    assert status["state"] == "paused"
    clock.advance(60.0)
    assert mgr.status()["elapsed_seconds"] == pytest.approx(3.0)
    mgr.resume(sid)
    clock.advance(2.0)
    assert mgr.status()["elapsed_seconds"] == pytest.approx(5.0)


def test_silence_warning_after_threshold(manager) -> None:
    mgr, _, clock = manager
    sid = mgr.start()["session_id"]
    mgr.append_chunk(sid, b"x", level=0.0)
    clock.advance(SILENCE_WARN_SECONDS + 1)
    status = mgr.append_chunk(sid, b"y", level=0.0)
    assert status["silence_warning"] is True
    status = mgr.append_chunk(sid, b"z", level=0.4)
    assert status["silence_warning"] is False
    assert status["silence_seconds"] == 0.0


def test_stop_without_audio_is_an_error(manager, tmp_path: Path) -> None:
    mgr, spy, _ = manager
    sid = mgr.start()["session_id"]
    with pytest.raises(RecordingError) as excinfo:
        mgr.stop(sid, {})
    assert excinfo.value.code == "recording_empty"
    assert spy.calls == []
    assert mgr.status() == {"state": "idle"}
    assert list(tmp_path.iterdir()) == []


def test_cancel_removes_partial_file(manager, tmp_path: Path) -> None:
    mgr, _, _ = manager
    sid = mgr.start()["session_id"]
    mgr.append_chunk(sid, b"abc", level=0.5)
    mgr.cancel(sid)
    assert mgr.status() == {"state": "idle"}
    assert list(tmp_path.iterdir()) == []


def test_size_limit_enforced(manager) -> None:
    mgr, _, _ = manager
    sid = mgr.start()["session_id"]
    with pytest.raises(RecordingError) as excinfo:
        mgr.append_chunk(sid, b"x" * 2048, level=0.5)
    assert excinfo.value.code == "recording_too_large"
    assert excinfo.value.http_status == 413
