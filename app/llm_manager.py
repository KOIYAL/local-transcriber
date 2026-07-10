"""Summary-model management backed by the modelshelf CLI.

modelshelf (https://github.com/koiyal/modelshelf) is a shared local-model
registry: it detects the machine's RAM/GPU, picks the best chat model from
a curated catalog, downloads it once into a store shared by every app on
the machine, and reports when a better model appears. This module drives
its JSON CLI the same way :mod:`app.model_manager` manages the Whisper
model: a background thread plus a pollable ``status()`` dict.

The feature is strictly optional: when the ``modelshelf`` binary is not on
PATH (and ``MODELSHELF_BIN`` is unset) the status is ``unavailable`` and
the app behaves exactly as before.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

APP_ID = "com.koiyal.local-transcriber"
TASK = "chat"
RECOMMEND_REF = f"sh.modelshelf.recommend.{TASK}"

# Generous ceilings; downloads can be GBs on slow lines.
METADATA_TIMEOUT = 60
DOWNLOAD_TIMEOUT = 4 * 60 * 60

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def _default_binary() -> str | None:
    override = os.getenv("MODELSHELF_BIN", "").strip()
    if override:
        return override if Path(override).exists() else None
    return shutil.which("modelshelf")


_UNSET: Any = object()


class LlmManager:
    """Provision and track the machine's recommended summary model."""

    def __init__(
        self,
        binary: str | None = _UNSET,
        runner: Runner = subprocess.run,
    ) -> None:
        self.binary = _default_binary() if binary is _UNSET else binary
        self._runner = runner
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._status = "unavailable" if self.binary is None else "not_started"
        self._message = (
            "modelshelf is not installed."
            if self.binary is None
            else "Summaries have not been set up yet."
        )
        self._progress = 0.0
        self._model_name: str | None = None
        self._model_path: Path | None = None
        self._upgrade: dict[str, Any] | None = None
        if self.binary is not None:
            self._adopt_existing()

    # -- modelshelf CLI ----------------------------------------------------

    def _run(self, *args: str, timeout: int = METADATA_TIMEOUT) -> dict | list | str:
        """Run the CLI and parse JSON output (or return raw text)."""
        assert self.binary is not None
        completed = self._runner(
            [self.binary, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip().splitlines()
            detail = stderr[-1] if stderr else f"exit code {completed.returncode}"
            raise RuntimeError(f"modelshelf {' '.join(args[:2])} failed: {detail}")
        text = (completed.stdout or "").strip()
        try:
            return json.loads(text)
        except ValueError:
            return text

    def _adopt_existing(self) -> None:
        """Offline-safe: become ready when a model was provisioned before.

        The provisioned model carries the reserved modelshelf ref
        ``sh.modelshelf.recommend.chat``; resolving it needs no network.
        """
        try:
            models = self._run("list", "--json")
            if not isinstance(models, list):
                return
            for model in models:
                refs = model.get("refs") or []
                if any(ref.get("app_id") == RECOMMEND_REF for ref in refs):
                    path = self._run("path", model["id"])
                    self._model_path = Path(str(path))
                    self._model_name = model.get("display_name")
                    self._status = "ready"
                    self._message = "Summaries are ready."
                    self._progress = 1.0
                    return
        except Exception:
            # Any surprise (old CLI, corrupt registry) just means "not set
            # up yet"; start() can still provision from scratch.
            return

    # -- public API ---------------------------------------------------------

    def start(self) -> None:
        """Kick off provisioning in the background (idempotent)."""
        with self._lock:
            if self.binary is None or self._status in {"ready", "downloading"}:
                return
            self._status = "downloading"
            self._message = "Choosing a summary model for this computer."
            self._progress = 0.0
            self._thread = threading.Thread(
                target=self._provision,
                name="summary-model-setup",
                daemon=True,
            )
            self._thread.start()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "available": self.binary is not None,
                "ready": self._status == "ready",
                "status": self._status,
                "progress": round(self._progress, 3),
                "message": self._message,
                "model": self._model_name,
                "upgrade": self._upgrade,
            }

    def model_path(self) -> Path | None:
        with self._lock:
            return self._model_path

    # -- provisioning -------------------------------------------------------

    def _set(self, status: str, progress: float, message: str) -> None:
        with self._lock:
            self._status = status
            self._progress = max(0.0, min(progress, 1.0))
            self._message = message

    def _provision(self) -> None:
        try:
            # 1. What would be downloaded? (drives the progress denominator
            #    and refreshes the catalog opportunistically)
            report = self._run("recommend", "--task", TASK, "--json")
            expected = 1
            if isinstance(report, dict):
                self._upgrade = report.get("upgrade")
                best = report.get("best")
                for item in report.get("items", []):
                    if item.get("entry", {}).get("name") == best:
                        entry = item["entry"]
                        expected = entry.get("file_bytes", 0) + sum(
                            extra.get("file_bytes", 0)
                            for extra in entry.get("extra_files", [])
                        )

            # 2. Download (resumable; reuses byte-identical local copies).
            #    Progress: poll the shared store's partial-download files,
            #    like model_manager does for Whisper downloads.
            shelf_home = Path(str(self._run("path")))
            done = threading.Event()
            poller = threading.Thread(
                target=self._poll_progress,
                args=(shelf_home / "downloads", max(expected, 1), done),
                daemon=True,
            )
            poller.start()
            try:
                result = self._run(
                    "recommend",
                    "--task",
                    TASK,
                    "--pull",
                    "--json",
                    timeout=DOWNLOAD_TIMEOUT,
                )
            finally:
                done.set()
                poller.join(timeout=5)

            if not isinstance(result, dict) or "path" not in result:
                raise RuntimeError("unexpected modelshelf output")
            model = result["model"]
            model_path = Path(result["path"])
            if not model_path.exists():
                raise RuntimeError("the downloaded model is missing")

            # 3. Declare our usage so `modelshelf gc` never collects it.
            self._run("refs", "add", model["id"], "--app", APP_ID, "--alias", "summary-model")

            with self._lock:
                self._model_path = model_path
                self._model_name = model.get("display_name")
            self._set("ready", 1.0, "Summaries are ready.")
        except Exception as exc:
            self._set("failed", 1.0, "The summary model could not be prepared.")
            with self._lock:
                self._message = f"The summary model could not be prepared. ({exc})"

    def _poll_progress(self, downloads_dir: Path, expected: int, done: threading.Event) -> None:
        while not done.wait(1.0):
            try:
                partial = sum(
                    entry.stat().st_size
                    for entry in downloads_dir.glob("*.part")
                    if entry.is_file()
                )
            except OSError:
                continue
            if partial > 0:
                fraction = min(partial / expected, 0.97)
                self._set(
                    "downloading",
                    fraction,
                    "Downloading the summary model.",
                )
