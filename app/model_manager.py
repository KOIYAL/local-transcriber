from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Any

from app.config import Settings
from app.system_info import select_model_for_memory, total_memory_bytes


MODEL_DOWNLOAD_BYTES = {
    "tiny": 75 * 1024**2,
    "base": 145 * 1024**2,
    "small": 466 * 1024**2,
    "medium": 1_500 * 1024**2,
}


class ModelManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory_bytes = total_memory_bytes()
        self.model_name = (
            "local"
            if settings.local_model
            else select_model_for_memory(self.memory_bytes)
        )
        self.model_path = (
            settings.local_model
            if settings.local_model
            else settings.model_dir / f"faster-whisper-{self.model_name}"
        )
        self._status = "ready" if self._is_ready() else "not_started"
        self._message = (
            "Transcription is ready."
            if self._status == "ready"
            else "Starting first-time setup."
        )
        self._error: str | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _is_ready(self) -> bool:
        if not self.model_path:
            return False
        required = ("config.json", "model.bin", "tokenizer.json")
        return self.model_path.is_dir() and all(
            (self.model_path / filename).exists() for filename in required
        )

    def start(self) -> None:
        with self._lock:
            if self._status in {"ready", "downloading"}:
                return
            self._status = "downloading"
            self._message = "Preparing the transcription model."
            self._error = None
            self._thread = threading.Thread(
                target=self._download,
                name="model-setup",
                daemon=True,
            )
            self._thread.start()

    def _download(self) -> None:
        try:
            if self.model_name == "local":
                if not self._is_ready():
                    raise RuntimeError("The configured local model could not be loaded.")
            else:
                from faster_whisper.utils import download_model

                assert self.model_path is not None
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                if self.model_path.exists() and not self._is_ready():
                    shutil.rmtree(self.model_path, ignore_errors=True)
                download_model(
                    self.model_name,
                    output_dir=str(self.model_path),
                    cache_dir=str(self.settings.model_dir / ".cache"),
                )
                if not self._is_ready():
                    raise RuntimeError("The model download did not complete.")
            with self._lock:
                self._status = "ready"
                self._message = "Transcription is ready."
        except Exception as exc:
            with self._lock:
                self._status = "failed"
                self._message = "The model could not be prepared."
                self._error = str(exc)

    def _downloaded_bytes(self) -> int:
        if not self.model_path or not self.model_path.exists():
            return 0
        return sum(
            path.stat().st_size
            for path in self.model_path.rglob("*")
            if path.is_file()
        )

    def status(self) -> dict[str, Any]:
        with self._lock:
            status = self._status
            message = self._message
            error = self._error

        if status == "downloading":
            expected = MODEL_DOWNLOAD_BYTES.get(self.model_name, 1)
            progress = min(self._downloaded_bytes() / expected, 0.97)
        elif status == "ready":
            progress = 1.0
        else:
            progress = 0.0

        return {
            "status": status,
            "message": message,
            "error": error,
            "progress": round(progress, 3),
            "model": self.model_name,
            "memory_gb": round(self.memory_bytes / 1024**3),
            "ready": status == "ready",
        }
