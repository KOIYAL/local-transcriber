import logging
import threading

from app import jobs
from app.jobs import JobManager, JobRecord
from test_jobs import make_settings


def test_stall_threshold_rate_limit_progress_and_inactive_jobs(tmp_path, monkeypatch, caplog):
    now = [0.0]
    dumps = []
    monkeypatch.setattr(jobs, "dump_stacks", lambda: dumps.append(now[0]))
    manager = JobManager(make_settings(tmp_path), clock=lambda: now[0], watchdog_interval=3600)
    try:
        for status in ("queued", "transcribing", "completed", "failed"):
            manager._jobs[status] = JobRecord(id=status, original_filename="PRIVATE.wav",
                                            media_path=tmp_path / "PRIVATE.wav", options={})
            manager._update(status, status, .12, "PRIVATE_PROGRESS")
        with caplog.at_level(logging.WARNING, logger="app.jobs"):
            now[0] = 299
            manager._check_stalled()
            assert not dumps
            now[0] = 300
            manager._check_stalled()
            manager._check_stalled()
            assert dumps == [300]
            assert len(caplog.records) == 1
            assert "job=transcribing stage=transcribing seconds=300.0" in caplog.text
            assert "PRIVATE" not in caplog.text
            now[0] = 899
            manager._check_stalled()
            assert dumps == [300]
            now[0] = 900
            manager._check_stalled()
            assert dumps == [300, 900]
            manager._update("transcribing", "diarizing", .9, "PRIVATE_PROGRESS")
            now[0] = 1199
            manager._check_stalled()
            assert len(dumps) == 2
            now[0] = 1500
            manager._check_stalled()
            assert dumps == [300, 900, 1500]
            manager._update("transcribing", "completed", 1, "done")
            now[0] = 2400
            manager._check_stalled()
            assert len(dumps) == 3
    finally:
        manager.shutdown()
    assert not manager._watchdog.is_alive()


def test_watchdog_thread_is_daemon_and_shutdown_wakes_it(tmp_path, monkeypatch):
    checked = threading.Event()
    monkeypatch.setattr(JobManager, "_check_stalled", lambda self: checked.set())
    manager = JobManager(make_settings(tmp_path), watchdog_interval=.01)
    try:
        assert manager._watchdog.daemon
        assert checked.wait(2)
    finally:
        manager.shutdown()
    assert not manager._watchdog.is_alive()
