"""Desktop diagnostics containing operational metadata only."""
from __future__ import annotations

import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
from pathlib import Path
import traceback

from app.config import Settings
from app.system_info import total_memory_bytes


CRASH_LOG_ENV = "LT_CRASH_LOG"
_crash_file = None  # Keep the descriptor alive for native crashes and watchdog dumps.
_handler = None


def setup_logging(settings: Settings, version: str) -> None:
    global _crash_file, _handler
    if _handler is not None:
        return
    directory = settings.data_dir / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    _crash_file = (directory / "crash.log").open("a", encoding="utf-8")
    faulthandler.enable(file=_crash_file, all_threads=True)
    # spawn children (speaker diarization) do not inherit faulthandler; they
    # read this variable and enable it themselves (enable_child_crash_log).
    os.environ[CRASH_LOG_ENV] = str(directory / "crash.log")
    _handler = RotatingFileHandler(
        directory / "backend.log", maxBytes=1024 * 1024, backupCount=3,
        encoding="utf-8",
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    # Third-party libraries can log decoded speech, prompts and local paths.
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    logger.addHandler(_handler)
    logger.propagate = False
    try:
        memory_gib = round(total_memory_bytes() / 1024**3, 2)
    except (OSError, ValueError):
        memory_gib = None
    logger.info(
        "startup version=%s os=%s arch=%s python=%s cpus=%s memory_gib=%s "
        "device=%s compute_type=%s", version, platform.system(), platform.machine(),
        platform.python_version(), os.cpu_count(), memory_gib,
        settings.device, settings.compute_type,
    )


def dump_stacks() -> None:
    if _crash_file is not None:
        faulthandler.dump_traceback(file=_crash_file, all_threads=True)


def log_failure(logger: logging.Logger, event: str, exc: Exception, *, job_id: str) -> None:
    # Exception messages, source lines and locals can contain user content.
    # Record frame locations only, including chained exceptions, without formatting them.
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        frames = "\n".join(
            f"  {Path(frame.filename).name}:{frame.lineno} in {frame.name}"
            for frame in traceback.extract_tb(exc.__traceback__)
        )
        logger.error("%s job=%s exception=%s\nTraceback:\n%s",
                     event, job_id, type(exc).__name__, frames)
        exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)


def enable_child_crash_log() -> None:
    """Record native crashes of a spawn child (e.g. sherpa-onnx) in crash.log."""
    global _crash_file
    path = os.environ.get(CRASH_LOG_ENV)
    if not path or _crash_file is not None:
        return
    try:
        _crash_file = open(path, "a", encoding="utf-8")
        faulthandler.enable(file=_crash_file, all_threads=True)
    except OSError:
        _crash_file = None
