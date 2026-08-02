from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Chunks are appended to disk the moment they arrive so that a crash never
# loses more than the single in-flight chunk. Meetings cannot be re-recorded,
# so durability beats elegance here (Phase 1 plan, decision 1).

MIME_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
}

# RMS levels (0..1) below this count as silence; recorder.js reports the level
# with every chunk so the tray/UI can warn while the meeting is still running.
SILENCE_LEVEL = 0.01
SILENCE_WARN_SECONDS = 30.0


class RecordingError(Exception):
    def __init__(self, code: str, http_status: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


@dataclass
class RecordingSession:
    id: str
    path: Path
    mime: str
    filename: str
    state: str = "recording"  # recording | paused
    bytes_written: int = 0
    active_seconds: float = 0.0
    active_since: float | None = None
    silence_since: float | None = None
    last_level: float | None = None


class RecordingManager:
    """Owns the single active microphone recording session.

    Phase 1 deliberately allows only one session at a time; the UI is a single
    record button and the tray mirrors this state machine 1:1.
    """

    def __init__(
        self,
        upload_dir: Path,
        submit_job: Callable[[str, Path, dict[str, Any]], Any],
        max_bytes: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.upload_dir = upload_dir
        self.submit_job = submit_job
        self.max_bytes = max_bytes
        self.clock = clock
        self._session: RecordingSession | None = None
        self._lock = threading.Lock()

    def start(self, mime: str = "audio/webm") -> dict[str, Any]:
        extension = MIME_EXTENSIONS.get(mime.split(";")[0].strip())
        if extension is None:
            raise RecordingError("unsupported_recording_mime", http_status=415)
        with self._lock:
            if self._session is not None:
                raise RecordingError("recording_in_progress")
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"recording-{stamp}{extension}"
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            path = self.upload_dir / f"{uuid.uuid4().hex}-{filename}"
            path.touch()
            self._session = RecordingSession(
                id=uuid.uuid4().hex,
                path=path,
                mime=mime,
                filename=filename,
                active_since=self.clock(),
            )
            return self._status_locked()

    def append_chunk(
        self,
        session_id: str,
        data: bytes,
        level: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            session = self._require(session_id)
            if session.bytes_written + len(data) > self.max_bytes:
                raise RecordingError("recording_too_large", http_status=413)
            if data:
                with session.path.open("ab") as handle:
                    handle.write(data)
                session.bytes_written += len(data)
            self._track_silence(session, level)
            return self._status_locked()

    def pause(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._require(session_id)
            if session.state == "recording" and session.active_since is not None:
                session.active_seconds += self.clock() - session.active_since
                session.active_since = None
                session.state = "paused"
                session.silence_since = None
            return self._status_locked()

    def resume(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._require(session_id)
            if session.state == "paused":
                session.active_since = self.clock()
                session.state = "recording"
            return self._status_locked()

    def stop(self, session_id: str, options: dict[str, Any]) -> Any:
        with self._lock:
            session = self._require(session_id)
            if session.bytes_written == 0:
                self._session = None
                session.path.unlink(missing_ok=True)
                raise RecordingError("recording_empty", http_status=400)
            self._session = None
        return self.submit_job(session.filename, session.path, options)

    def cancel(self, session_id: str) -> None:
        with self._lock:
            session = self._require(session_id)
            self._session = None
        session.path.unlink(missing_ok=True)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status_locked()

    def _require(self, session_id: str) -> RecordingSession:
        if self._session is None or self._session.id != session_id:
            raise RecordingError("recording_not_found", http_status=404)
        return self._session

    def _track_silence(self, session: RecordingSession, level: float | None) -> None:
        if level is None or session.state != "recording":
            return
        session.last_level = level
        if level < SILENCE_LEVEL:
            if session.silence_since is None:
                session.silence_since = self.clock()
        else:
            session.silence_since = None

    def _status_locked(self) -> dict[str, Any]:
        session = self._session
        if session is None:
            return {"state": "idle"}
        elapsed = session.active_seconds
        if session.active_since is not None:
            elapsed += self.clock() - session.active_since
        silence_seconds = 0.0
        if session.silence_since is not None:
            silence_seconds = self.clock() - session.silence_since
        return {
            "state": session.state,
            "session_id": session.id,
            "filename": session.filename,
            "elapsed_seconds": round(elapsed, 1),
            "bytes_written": session.bytes_written,
            "silence_seconds": round(silence_seconds, 1),
            "silence_warning": silence_seconds >= SILENCE_WARN_SECONDS,
        }
