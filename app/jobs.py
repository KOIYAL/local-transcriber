from __future__ import annotations

import shutil
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.config import Settings
from app.exporters import to_txt, write_exports
from app.diarizer import assign_speakers
from app.transcriber import TranscriptionEngine
from app.logging_setup import dump_stacks, log_failure


logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class JobRecord:
    id: str
    original_filename: str
    media_path: Path
    options: dict[str, Any]
    status: str = "queued"
    progress: float = 0.0
    message: str = "Waiting to start."
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    result: dict[str, Any] | None = None
    exports: dict[str, Path] = field(default_factory=dict)
    error: str | None = None
    summary: str | None = None
    summary_status: str = "none"  # none | queued | running | completed | failed
    summary_error: str | None = None
    progress_at: float | None = None  # Monotonic clock, independent of wall-clock changes.
    last_stall_dump: float | None = None

    def as_dict(self, include_result: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "filename": self.original_filename,
            "status": self.status,
            "progress": round(self.progress, 3),
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "options": self.options,
            "error": self.error,
        }
        if self.result and include_result:
            payload["result"] = self.result
        if self.summary_status != "none":
            payload["summary"] = {
                "status": self.summary_status,
                "text": self.summary if include_result else None,
                "error": self.summary_error,
            }
        if self.exports:
            payload["downloads"] = {
                file_format: f"/api/jobs/{self.id}/download/{file_format}"
                for file_format in self.exports
            }
        return payload


# Completed/failed jobs kept in memory (each holds its full transcript).
# Older ones are forgotten; their files under data/outputs stay on disk.
MAX_JOBS = 50

ACTIVE_STATUSES = {"queued", "loading_model", "transcribing", "diarizing", "finalizing"}


class JobManager:
    def __init__(self, settings: Settings, diarizer=None, *, clock=time.monotonic,
                 watchdog_interval=30, stall_seconds=300, dump_interval=600) -> None:
        self.settings = settings
        self.diarizer = diarizer
        self.engine = TranscriptionEngine(settings)
        self.executor = ThreadPoolExecutor(
            max_workers=settings.max_workers,
            thread_name_prefix="transcriber",
        )
        # Summaries run on their own single worker so a slow LLM never
        # blocks transcription jobs (and inference stays serialized).
        self.summary_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="summarizer",
        )
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._clock = clock
        self._stall_seconds = stall_seconds
        self._dump_interval = dump_interval
        self._watchdog_stop = threading.Event()
        self._watchdog = threading.Thread(
            target=self._watch, args=(watchdog_interval,), daemon=True,
            name="transcriber-watchdog",
        )
        self._watchdog.start()

    def _watch(self, interval: float) -> None:
        while not self._watchdog_stop.wait(interval):
            self._check_stalled()

    def _check_stalled(self) -> None:
        stalled = []
        with self._lock:
            now = self._clock()
            for job in self._jobs.values():
                if job.status not in ACTIVE_STATUSES - {"queued"} or job.progress_at is None:
                    continue
                elapsed = now - job.progress_at
                if elapsed < self._stall_seconds:
                    continue
                if job.last_stall_dump is not None and now - job.last_stall_dump < self._dump_interval:
                    continue
                job.last_stall_dump = now
                stalled.append((job.id, job.status, elapsed))
        for job_id, stage, elapsed in stalled:
            logger.warning("job_stalled job=%s stage=%s seconds=%.1f", job_id, stage, elapsed)
            dump_stacks()

    def submit(
        self,
        original_filename: str,
        media_path: Path,
        options: dict[str, Any],
    ) -> JobRecord:
        job = JobRecord(
            id=uuid.uuid4().hex,
            original_filename=original_filename,
            media_path=media_path,
            options=options,
        )
        with self._lock:
            self._jobs[job.id] = job
            self._prune_locked()
        self.executor.submit(self._run, job.id)
        return job

    def _prune_locked(self) -> None:
        """Forget the oldest finished jobs beyond MAX_JOBS (memory bound)."""
        finished = [
            job
            for job in self._jobs.values()
            if job.status not in ACTIVE_STATUSES
            and job.summary_status not in {"queued", "running"}
        ]
        excess = len(self._jobs) - MAX_JOBS
        if excess <= 0:
            return
        finished.sort(key=lambda job: job.created_at)
        for job in finished[:excess]:
            del self._jobs[job.id]

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[JobRecord]:
        with self._lock:
            jobs = list(self._jobs.values())
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)[:limit]

    def delete(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if (
                not job
                or job.status in ACTIVE_STATUSES
                or job.summary_status in {"queued", "running"}
            ):
                return False
            del self._jobs[job_id]
        shutil.rmtree(self.settings.output_dir / job_id, ignore_errors=True)
        job.media_path.unlink(missing_ok=True)
        return True

    def _update(
        self,
        job_id: str,
        status: str,
        progress: float,
        message: str,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = status
            job.progress = max(0.0, min(progress, 1.0))
            job.message = message
            job.updated_at = utc_now()
            job.progress_at = self._clock()

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]

        try:
            result = self.engine.transcribe(
                job.media_path,
                job.options,
                lambda status, progress, message: self._update(
                    job_id,
                    status,
                    progress,
                    message,
                ),
            )
            if job.options.get("diarize"):
                self._update(job_id, "diarizing", 0.90, "Separating speakers.")
                started = time.monotonic()
                logger.info("diarization_start job=%s", job_id)
                try:
                    if self.diarizer is None:
                        raise RuntimeError("Speaker diarization is unavailable")
                    turns = self.diarizer.diarize(
                        job.media_path,
                        lambda fraction: self._update(
                            job_id, "diarizing", 0.90 + 0.03 * max(0.0, min(1.0, fraction)),
                            "Separating speakers.",
                        ),
                    )
                    result["segments"] = assign_speakers(result["segments"], turns)
                    result["text"] = to_txt(result["segments"]).strip()
                    logger.info("diarization_end job=%s seconds=%.3f", job_id,
                                time.monotonic() - started)
                except Exception as exc:
                    log_failure(logger, "diarization_timeout" if isinstance(exc, TimeoutError)
                                else "diarization_failed", exc, job_id=job_id)
                    # Preserve useful transcription and the source on optional-feature failure.
                    result["diarization_failed"] = True
            self._update(job_id, "finalizing", 0.94, "Creating output files.")
            metadata = {
                key: value
                for key, value in result.items()
                if key not in {"text", "segments"}
            }
            metadata.update(
                {
                    "filename": job.original_filename,
                    "text": result["text"],
                }
            )
            exports = write_exports(
                self.settings.output_dir / job.id,
                metadata=metadata,
                segments=result["segments"],
            )
            with self._lock:
                stored_job = self._jobs[job_id]
                stored_job.result = result
                stored_job.exports = exports
            self._update(job_id, "completed", 1.0, "Transcription complete.")
            # The source is deleted only after a successful run. On failure
            # it stays in data/uploads: for an in-app recording it is the
            # only copy of the meeting, and a transient error (GPU runtime,
            # disk full) must not destroy it. DELETE /api/jobs/{id} or the
            # user removes it.
            if not self.settings.keep_uploads and not result.get("diarization_failed"):
                job.media_path.unlink(missing_ok=True)
        except Exception as exc:
            log_failure(logger, "job_failed", exc, job_id=job_id)
            self._update(job_id, "failed", 1.0, "Transcription failed.")
            with self._lock:
                self._jobs[job_id].error = str(exc)

    def submit_summary(
        self,
        job_id: str,
        run_summary: Callable[[str], str],
    ) -> JobRecord | None:
        """Queue a summary of a completed job's transcript.

        `run_summary` receives the transcript text and returns the summary
        (the caller binds the engine and model path). Returns the job, or
        None when it does not exist or has no completed transcript yet.
        Re-submitting while queued/running is a no-op.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "completed" or not job.result:
                return None
            if job.summary_status in {"queued", "running"}:
                return job
            job.summary_status = "queued"
            job.summary_error = None
            job.updated_at = utc_now()
        self.summary_executor.submit(self._run_summary, job_id, run_summary)
        return job

    def _set_summary(self, job_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.summary_status = status
            job.summary_error = error
            job.updated_at = utc_now()

    def _run_summary(self, job_id: str, run_summary: Callable[[str], str]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            text = (job.result or {}).get("text", "")
        self._set_summary(job_id, "running")
        try:
            summary = run_summary(text)
            output_dir = self.settings.output_dir / job_id
            output_dir.mkdir(parents=True, exist_ok=True)
            summary_path = output_dir / "summary.txt"
            summary_path.write_text(summary + "\n", encoding="utf-8")
            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                job.summary = summary
                job.exports["summary.txt"] = summary_path
            self._set_summary(job_id, "completed")
        except Exception as exc:
            log_failure(logger, "summary_failed", exc, job_id=job_id)
            self._set_summary(job_id, "failed", str(exc))

    def shutdown(self) -> None:
        self._watchdog_stop.set()
        self._watchdog.join(timeout=1)
        self.executor.shutdown(wait=False, cancel_futures=False)
        self.summary_executor.shutdown(wait=False, cancel_futures=False)
