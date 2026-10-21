from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    ALLOWED_EXTENSIONS,
    PROJECT_ROOT,
    SETTINGS,
)
from app.apple_intelligence import AppleIntelligenceEngine
from app.capture import RecordingError, RecordingManager
from app.discord_presence import DiscordPresence, build_activity
from app.diarizer import Diarizer
from app.jobs import JobManager
from app.llm_manager import LlmManager
from app.model_manager import ModelManager
from app.summarizer import SummaryEngine, llama_available
from app.update_checker import UpdateChecker

# Which summary engine to use: `auto` prefers Apple Intelligence when the
# machine supports it and falls back to the local LLM; `apple` / `local`
# force one of them.
SUMMARY_ENGINE_ENV = "LT_SUMMARY_ENGINE"


@asynccontextmanager
async def lifespan(app: FastAPI):
    for directory in (
        SETTINGS.upload_dir,
        SETTINGS.output_dir,
        SETTINGS.model_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    app.state.update_checker = UpdateChecker(SETTINGS.data_dir)
    app.state.models = ModelManager(SETTINGS)
    app.state.diarizer = Diarizer(SETTINGS.model_dir)
    app.state.jobs = JobManager(SETTINGS, diarizer=app.state.diarizer)
    app.state.recorder = RecordingManager(
        SETTINGS.upload_dir,
        submit_job=app.state.jobs.submit,
        max_bytes=SETTINGS.max_upload_bytes,
    )
    app.state.summary_llm = LlmManager()
    app.state.summarizer = SummaryEngine()
    app.state.apple_ai = AppleIntelligenceEngine()
    # Discord Rich Presence (optional; silent no-op when APP_ID is empty,
    # Discord is not running, or LT_DISCORD_PRESENCE=off. Never shows file
    # names or transcript content).
    app.state.discord = DiscordPresence(
        activity_provider=lambda: build_activity(app.state.jobs)
    )
    app.state.discord.start()
    yield
    app.state.discord.stop()
    app.state.jobs.shutdown()


app = FastAPI(
    title="Local Transcriber",
    version="0.7.0",
    lifespan=lifespan,
)
app.mount(
    "/static",
    StaticFiles(directory=PROJECT_ROOT / "app" / "static"),
    name="static",
)

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Slack for the multipart envelope around the media file itself.
UPLOAD_ENVELOPE_BYTES = 1024 * 1024


def _host_only(authority: str | None) -> str:
    """`127.0.0.1:8000` -> `127.0.0.1`, `[::1]:8000` -> `[::1]`."""
    if not authority:
        return ""
    value = authority.strip().lower()
    if value.startswith("["):
        return value.split("]", 1)[0] + "]"
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


@app.middleware("http")
async def local_only_guard(request: Request, call_next):
    """Keep the API usable only by this computer's own pages.

    Binding to 127.0.0.1 stops remote hosts, but not a web page the user
    happens to have open: DNS rebinding (a hostname that resolves to
    127.0.0.1) and plain cross-site requests would otherwise reach a
    fixed-port backend. So: the Host header must be a loopback name, and a
    state-changing request that carries an Origin must come from exactly
    the host the page was served from. Clients without an Origin header
    (the Electron shell's own fetches send one; curl and tests do not) are
    local by construction.
    """
    host = request.headers.get("host")
    if _host_only(host) not in LOOPBACK_HOSTS:
        return JSONResponse(status_code=421, content={"detail": error_detail("bad_host")})
    if request.method not in SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin and origin != "null":
            if urlsplit(origin).netloc.lower() != (host or "").strip().lower():
                return JSONResponse(
                    status_code=403, content={"detail": error_detail("bad_origin")}
                )
        # Reject oversized uploads before Starlette spools the multipart
        # body to a temp file; the per-chunk check in create_job remains
        # the backstop for requests without a Content-Length.
        if request.url.path == "/api/jobs" and request.method == "POST":
            length = request.headers.get("content-length", "")
            if length.isdigit() and int(length) > SETTINGS.max_upload_bytes + UPLOAD_ENVELOPE_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": error_detail(
                            "file_too_large",
                            size=SETTINGS.max_upload_bytes // (1024 * 1024),
                        )
                    },
                )
    return await call_next(request)


def job_manager(request: Request) -> JobManager:
    return request.app.state.jobs


def model_manager(request: Request) -> ModelManager:
    return request.app.state.models


def recording_manager(request: Request) -> RecordingManager:
    return request.app.state.recorder


def llm_manager(request: Request) -> LlmManager:
    return request.app.state.summary_llm


def summary_status(request: Request) -> dict:
    """Feature status for clients, after engine selection.

    Apple Intelligence wins when available (no setup, no download);
    otherwise the local engine needs both modelshelf AND llama-cpp.
    """
    mode = os.getenv(SUMMARY_ENGINE_ENV, "auto").strip().lower()
    if mode != "local" and request.app.state.apple_ai.available():
        return {
            "available": True,
            "ready": True,
            "status": "ready",
            "progress": 1.0,
            "message": "Summaries are ready.",
            "model": "Apple Intelligence",
            "upgrade": None,
            "engine": "apple_intelligence",
        }
    if mode == "apple":
        return {
            "available": False,
            "ready": False,
            "status": "unavailable",
            "progress": 0.0,
            "message": "Apple Intelligence is not available on this machine.",
            "model": None,
            "upgrade": None,
            "engine": "apple_intelligence",
        }
    status = llm_manager(request).status()
    if not llama_available():
        status["available"] = False
        status["ready"] = False
    status["engine"] = "local_llm"
    return status


def error_detail(code: str, **params: str | int) -> dict:
    return {"code": code, "params": params}


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "static" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/update-check")
def update_check(request: Request) -> dict:
    # Run urllib in FastAPI's worker pool so recording chunks stay responsive.
    return request.app.state.update_checker.check(request.app.version)


@app.get("/api/config")
async def config(request: Request) -> dict:
    setup = model_manager(request).status()
    return {
        "max_upload_mb": SETTINGS.max_upload_bytes // (1024 * 1024),
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "setup": setup,
        "summary": summary_status(request),
        "diarize": request.app.state.diarizer.status(),
    }


@app.get("/api/diarize/setup")
async def diarize_setup(request: Request) -> dict:
    return request.app.state.diarizer.status()


@app.post("/api/diarize/setup", status_code=202)
async def start_diarize_setup(request: Request) -> dict:
    # Unlike automatic Whisper setup, this download requires an explicit opt-in.
    request.app.state.diarizer.start()
    return request.app.state.diarizer.status()


def _check_diarize(request: Request, enabled: bool) -> None:
    if enabled and not request.app.state.diarizer.status()["ready"]:
        raise HTTPException(status_code=409, detail=error_detail("diarize_setup_incomplete"))


def _start_summary_setup(request: Request) -> dict:
    status = summary_status(request)
    # Only the local engine needs provisioning; Apple Intelligence is a
    # system service with nothing to download.
    if status["engine"] == "local_llm" and status["available"] and llama_available():
        llm_manager(request).start()
        status = summary_status(request)
    return status


@app.get("/api/summary/setup")
async def summary_setup(request: Request) -> dict:
    return _start_summary_setup(request)


@app.post("/api/summary/setup/retry")
async def retry_summary_setup(request: Request) -> dict:
    return _start_summary_setup(request)


@app.get("/api/setup")
async def setup(request: Request) -> dict:
    manager = model_manager(request)
    manager.start()
    return manager.status()


@app.post("/api/setup/retry")
async def retry_setup(request: Request) -> dict:
    manager = model_manager(request)
    manager.start()
    return manager.status()


@app.get("/api/models/upgrade-check")
async def models_upgrade_check(request: Request) -> dict:
    return model_manager(request).upgrade_check()


@app.post("/api/models/upgrade", status_code=202)
async def models_upgrade(request: Request) -> dict:
    try:
        return model_manager(request).upgrade_to_recommended()
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": str(exc), "message": "The model cannot be upgraded now."},
        ) from exc


@app.get("/api/jobs")
async def list_jobs(request: Request) -> dict:
    # Summaries only: the tray polls this every second, and a completed
    # job's full transcript belongs in GET /api/jobs/{id}.
    jobs = job_manager(request).list_recent()
    return {"jobs": [job.as_dict(include_result=False) for job in jobs]}


@app.post("/api/jobs", status_code=202)
async def create_job(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    vad_filter: Annotated[bool, Form()] = True,
    glossary: Annotated[str, Form()] = "",
    diarize: Annotated[bool, Form()] = False,
) -> dict:
    _check_diarize(request, diarize)
    original_name = Path(file.filename or "upload").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=415,
            detail=error_detail("unsupported_extension", allowed=allowed),
        )
    setup_state = model_manager(request).status()
    if not setup_state["ready"]:
        raise HTTPException(
            status_code=409,
            detail=error_detail("setup_incomplete"),
        )
    stored_path = SETTINGS.upload_dir / f"{uuid.uuid4().hex}{extension}"
    size = 0
    try:
        with stored_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > SETTINGS.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=error_detail(
                            "file_too_large",
                            size=SETTINGS.max_upload_bytes // (1024 * 1024),
                        ),
                    )
                destination.write(chunk)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if size == 0:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=error_detail("empty_file"),
        )

    options = {
        "model": setup_state["model"],
        "language": None,
        "task": "transcribe",
        "vad_filter": vad_filter,
        "beam_size": 5,
        "initial_prompt": glossary.strip()[:500],
        "diarize": diarize,
    }
    job = job_manager(request).submit(original_name, stored_path, options)
    return job.as_dict()


def _recording_http_error(exc: RecordingError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=error_detail(exc.code))


@app.get("/api/recording/status")
async def recording_status(request: Request) -> dict:
    return recording_manager(request).status()


@app.post("/api/recording/start", status_code=201)
async def start_recording(
    request: Request,
    mime: Annotated[str, Form()] = "audio/webm",
) -> dict:
    # Recording is gated on a ready model on purpose: it is kinder to fail
    # before the meeting starts than to discover after it that the recording
    # cannot be transcribed.
    if not model_manager(request).status()["ready"]:
        raise HTTPException(status_code=409, detail=error_detail("setup_incomplete"))
    try:
        return recording_manager(request).start(mime)
    except RecordingError as exc:
        raise _recording_http_error(exc) from exc


@app.post("/api/recording/{session_id}/chunk")
async def append_recording_chunk(session_id: str, request: Request) -> dict:
    data = await request.body()
    level_header = request.headers.get("x-audio-level")
    level: float | None = None
    if level_header is not None:
        try:
            level = max(0.0, min(1.0, float(level_header)))
        except ValueError:
            level = None
    try:
        return recording_manager(request).append_chunk(session_id, data, level)
    except RecordingError as exc:
        raise _recording_http_error(exc) from exc


@app.post("/api/recording/{session_id}/pause")
async def pause_recording(session_id: str, request: Request) -> dict:
    try:
        return recording_manager(request).pause(session_id)
    except RecordingError as exc:
        raise _recording_http_error(exc) from exc


@app.post("/api/recording/{session_id}/resume")
async def resume_recording(session_id: str, request: Request) -> dict:
    try:
        return recording_manager(request).resume(session_id)
    except RecordingError as exc:
        raise _recording_http_error(exc) from exc


@app.post("/api/recording/{session_id}/stop", status_code=202)
async def stop_recording(
    session_id: str,
    request: Request,
    vad_filter: Annotated[bool, Form()] = True,
    glossary: Annotated[str, Form()] = "",
    diarize: Annotated[bool, Form()] = False,
) -> dict:
    # Always accept saved recording chunks. If optional models became unavailable,
    # JobManager keeps the ordinary transcript and source instead of rejecting stop.
    setup_state = model_manager(request).status()
    options = {
        "model": setup_state["model"],
        "language": None,
        "task": "transcribe",
        "vad_filter": vad_filter,
        "beam_size": 5,
        "initial_prompt": glossary.strip()[:500],
        "diarize": diarize,
    }
    try:
        job = recording_manager(request).stop(session_id, options)
    except RecordingError as exc:
        raise _recording_http_error(exc) from exc
    return job.as_dict()


@app.delete("/api/recording/{session_id}", status_code=204)
async def cancel_recording(session_id: str, request: Request) -> None:
    try:
        recording_manager(request).cancel(session_id)
    except RecordingError as exc:
        raise _recording_http_error(exc) from exc


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    job = job_manager(request).get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=error_detail("job_not_found"),
        )
    return job.as_dict()


@app.get("/api/jobs/{job_id}/download/{file_format}")
async def download(job_id: str, file_format: str, request: Request) -> FileResponse:
    job = job_manager(request).get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=error_detail("job_not_found"),
        )
    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=error_detail("job_incomplete"),
        )
    path = job.exports.get(file_format)
    if not path or not path.exists():
        raise HTTPException(
            status_code=404,
            detail=error_detail("output_missing"),
        )
    stem = Path(job.original_filename).stem
    return FileResponse(
        path,
        filename=f"{stem}.{file_format}",
        media_type="application/octet-stream",
    )


@app.post("/api/jobs/{job_id}/summarize", status_code=202)
async def summarize_job(job_id: str, request: Request) -> dict:
    job = job_manager(request).get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=error_detail("job_not_found"),
        )
    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=error_detail("job_incomplete"),
        )
    status = summary_status(request)
    if not status["ready"]:
        raise HTTPException(
            status_code=409,
            detail=error_detail("summary_setup_incomplete"),
        )
    if status["engine"] == "apple_intelligence":
        apple = request.app.state.apple_ai
        submitted = job_manager(request).submit_summary(job_id, apple.summarize)
        if submitted is None:
            raise HTTPException(
                status_code=409,
                detail=error_detail("job_incomplete"),
            )
        return submitted.as_dict()

    model_path = llm_manager(request).model_path()
    if model_path is None:
        raise HTTPException(
            status_code=409,
            detail=error_detail("summary_setup_incomplete"),
        )
    engine = request.app.state.summarizer
    submitted = job_manager(request).submit_summary(
        job_id,
        lambda text: engine.summarize(text, model_path),
    )
    if submitted is None:
        raise HTTPException(
            status_code=409,
            detail=error_detail("job_incomplete"),
        )
    return submitted.as_dict()


@app.delete("/api/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request) -> None:
    if not job_manager(request).delete(job_id):
        raise HTTPException(
            status_code=409,
            detail=error_detail("job_busy"),
        )
