from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    ALLOWED_EXTENSIONS,
    PROJECT_ROOT,
    SETTINGS,
)
from app.jobs import JobManager
from app.model_manager import ModelManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    for directory in (
        SETTINGS.upload_dir,
        SETTINGS.output_dir,
        SETTINGS.model_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    app.state.models = ModelManager(SETTINGS)
    app.state.jobs = JobManager(SETTINGS)
    yield
    app.state.jobs.shutdown()


app = FastAPI(
    title="Local Transcriber",
    version="0.4.0",
    lifespan=lifespan,
)
app.mount(
    "/static",
    StaticFiles(directory=PROJECT_ROOT / "app" / "static"),
    name="static",
)


def job_manager(request: Request) -> JobManager:
    return request.app.state.jobs


def model_manager(request: Request) -> ModelManager:
    return request.app.state.models


def error_detail(code: str, **params: str | int) -> dict:
    return {"code": code, "params": params}


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app" / "static" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
async def config(request: Request) -> dict:
    setup = model_manager(request).status()
    return {
        "max_upload_mb": SETTINGS.max_upload_bytes // (1024 * 1024),
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "setup": setup,
    }


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


@app.get("/api/jobs")
async def list_jobs(request: Request) -> dict:
    jobs = job_manager(request).list_recent()
    return {"jobs": [job.as_dict() for job in jobs]}


@app.post("/api/jobs", status_code=202)
async def create_job(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    vad_filter: Annotated[bool, Form()] = True,
) -> dict:
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
        "initial_prompt": "",
    }
    job = job_manager(request).submit(original_name, stored_path, options)
    return job.as_dict()


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


@app.delete("/api/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request) -> None:
    if not job_manager(request).delete(job_id):
        raise HTTPException(
            status_code=409,
            detail=error_detail("job_busy"),
        )
