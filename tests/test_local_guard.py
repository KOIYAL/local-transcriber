"""The API answers this computer's own pages only (Host / Origin guard)."""

from fastapi.testclient import TestClient

from app.main import app


def test_non_loopback_host_is_refused() -> None:
    with TestClient(app, base_url="http://attacker.example") as client:
        response = client.get("/api/health")
        assert response.status_code == 421
        assert response.json()["detail"]["code"] == "bad_host"


def test_loopback_hosts_with_ports_are_accepted() -> None:
    for base in ("http://127.0.0.1:8000", "http://localhost:8000"):
        with TestClient(app, base_url=base) as client:
            assert client.get("/api/health").status_code == 200
    # The test client cannot dial an IPv6 literal; check the header form.
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/api/health", headers={"Host": "[::1]:8000"})
        assert response.status_code == 200


def test_cross_origin_state_change_is_refused() -> None:
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/recording/start",
            headers={"Origin": "http://evil.example"},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "bad_origin"
        # Another local port is another app: still refused.
        response = client.post(
            "/api/recording/start",
            headers={"Origin": "http://127.0.0.1:9999"},
        )
        assert response.status_code == 403


def test_same_origin_and_originless_requests_pass_the_guard() -> None:
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        app.state.models.status = lambda: {"ready": False, "model": "tiny"}
        # Same origin: reaches the handler (which refuses for its own reason).
        response = client.post(
            "/api/recording/start",
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        assert response.json()["detail"]["code"] == "setup_incomplete"
        # No Origin header (curl, scripts): also reaches the handler.
        response = client.post("/api/recording/start")
        assert response.json()["detail"]["code"] == "setup_incomplete"


def test_oversized_upload_is_refused_before_parsing() -> None:
    from app.config import SETTINGS

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/api/jobs",
            headers={
                "Content-Length": str(SETTINGS.max_upload_bytes + 2 * 1024 * 1024),
                "Content-Type": "multipart/form-data; boundary=x",
            },
        )
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "file_too_large"


def test_job_list_omits_results() -> None:
    from pathlib import Path

    from app.jobs import JobRecord

    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        job = JobRecord(
            id="list-job",
            original_filename="m.wav",
            media_path=Path("m.wav"),
            options={},
            status="completed",
            result={"text": "secret", "segments": []},
        )
        with app.state.jobs._lock:
            app.state.jobs._jobs[job.id] = job
        listed = client.get("/api/jobs").json()["jobs"]
        entry = next(item for item in listed if item["id"] == "list-job")
        assert "result" not in entry
        assert client.get("/api/jobs/list-job").json()["result"]["text"] == "secret"
