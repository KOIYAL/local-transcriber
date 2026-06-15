from fastapi.testclient import TestClient

from app.main import app


def test_health_and_config() -> None:
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        response = client.get("/api/config")
        assert response.status_code == 200
        payload = response.json()
        assert payload["max_upload_mb"] > 0
        assert payload["setup"]["model"] in {"tiny", "base", "small", "medium", "local"}


def test_rejects_unsupported_extension() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs",
            files={"file": ("sample.txt", b"not media", "text/plain")},
            data={"model": "tiny"},
        )
        assert response.status_code == 415
        detail = response.json()["detail"]
        assert detail["code"] == "unsupported_extension"
        assert ".mp3" in detail["params"]["allowed"]
