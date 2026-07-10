"""Summary endpoints, with the LLM manager and engine faked out."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.jobs import JobRecord
from app.main import app


class FakeLlm:
    def __init__(self, ready: bool, model_path: Path | None) -> None:
        self._ready = ready
        self._model_path = model_path
        self.started = 0

    def status(self) -> dict:
        return {
            "available": True,
            "ready": self._ready,
            "status": "ready" if self._ready else "not_started",
            "progress": 1.0 if self._ready else 0.0,
            "message": "",
            "model": "fake-model" if self._ready else None,
            "upgrade": None,
        }

    def model_path(self) -> Path | None:
        return self._model_path

    def start(self) -> None:
        self.started += 1


class FakeEngine:
    def summarize(self, text: str, model_path: Path) -> str:
        return f"SUMMARY[{len(text)} chars via {model_path.name}]"


def inject_completed_job(job_id: str, tmp_path: Path) -> JobRecord:
    job = JobRecord(
        id=job_id,
        original_filename="meeting.wav",
        media_path=tmp_path / "meeting.wav",
        options={},
        status="completed",
        progress=1.0,
        result={"text": "Hello world. This is a transcript.", "segments": []},
    )
    with app.state.jobs._lock:
        app.state.jobs._jobs[job_id] = job
    return job


def wait_for_summary(client: TestClient, job_id: str) -> dict:
    for _ in range(200):
        payload = client.get(f"/api/jobs/{job_id}").json()
        state = payload.get("summary", {}).get("status")
        if state in {"completed", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("summary never finished")


def test_config_exposes_summary_feature_block() -> None:
    with TestClient(app) as client:
        payload = client.get("/api/config").json()
        assert "summary" in payload
        assert isinstance(payload["summary"]["available"], bool)


def test_summarize_full_flow_with_fakes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.llama_available", lambda: True)
    with TestClient(app) as client:
        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"GGUF")
        app.state.summary_llm = FakeLlm(ready=True, model_path=model_file)
        app.state.summarizer = FakeEngine()
        inject_completed_job("sum-ok", tmp_path)

        response = client.post("/api/jobs/sum-ok/summarize")
        assert response.status_code == 202, response.text

        payload = wait_for_summary(client, "sum-ok")
        assert payload["summary"]["status"] == "completed"
        assert payload["summary"]["text"].startswith("SUMMARY[")
        assert "summary.txt" in payload["downloads"]

        download = client.get(payload["downloads"]["summary.txt"])
        assert download.status_code == 200
        assert b"SUMMARY[" in download.content

        # Cleanup removes the job's output directory (incl. summary.txt).
        assert client.delete("/api/jobs/sum-ok").status_code == 204


def test_summarize_refusals(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.main.llama_available", lambda: True)
    with TestClient(app) as client:
        # Unknown job.
        assert client.post("/api/jobs/missing/summarize").status_code == 404

        # LLM not ready yet.
        app.state.summary_llm = FakeLlm(ready=False, model_path=None)
        app.state.summarizer = FakeEngine()
        inject_completed_job("sum-wait", tmp_path)
        response = client.post("/api/jobs/sum-wait/summarize")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "summary_setup_incomplete"

        # Job not completed.
        app.state.summary_llm = FakeLlm(ready=True, model_path=tmp_path / "m.gguf")
        (tmp_path / "m.gguf").write_bytes(b"GGUF")
        job = inject_completed_job("sum-early", tmp_path)
        job.status = "transcribing"
        response = client.post("/api/jobs/sum-early/summarize")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "job_incomplete"

        # Cleanup.
        job.status = "completed"
        client.delete("/api/jobs/sum-wait")
        client.delete("/api/jobs/sum-early")
