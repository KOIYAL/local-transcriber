from __future__ import annotations

import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.exporters import write_exports
from app.transcriber import TranscriptionEngine


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

    def as_dict(self) -> dict[str, Any]:
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
        if self.result:
            payload["result"] = self.result
        if self.exports:
            payload["downloads"] = {
                file_format: f"/api/jobs/{self.id}/download/{file_format}"
                for file_format in self.exports
            }
        return payload


class JobManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = TranscriptionEngine(settings)
        self.executor = ThreadPoolExecutor(
            max_workers=settings.max_workers,
            thread_name_prefix="transcriber",
        )
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

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
        self.executor.submit(self._run, job.id)
        return job

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
            active_statuses = {
                "queued",
                "loading_model",
                "transcribing",
                "finalizing",
            }
            if not job or job.status in active_statuses:
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
        except Exception as exc:
            self._update(job_id, "failed", 1.0, "Transcription failed.")
            with self._lock:
                self._jobs[job_id].error = str(exc)
        finally:
            if not self.settings.keep_uploads:
                job.media_path.unlink(missing_ok=True)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)
