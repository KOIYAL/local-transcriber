from fastapi.testclient import TestClient

from app.main import app


def test_health_and_config() -> None:
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        response = client.get("/api/config")
        assert response.status_code == 200
        payload = response.json()
        assert payload["max_upload_mb"] > 0
        assert payload["setup"]["model"] in {"tiny", "base", "small", "medium", "turbo", "local"}


def test_rejects_unsupported_extension() -> None:
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/jobs",
            files={"file": ("sample.txt", b"not media", "text/plain")},
            data={"model": "tiny"},
        )
        assert response.status_code == 415
        detail = response.json()["detail"]
        assert detail["code"] == "unsupported_extension"
        assert ".mp3" in detail["params"]["allowed"]


def test_form_bool_defaults_do_not_depend_on_fastapi_version() -> None:
    from app.main import form_bool

    assert form_bool(None, default=True) is True
    assert form_bool("", default=True) is True
    assert form_bool("false", default=True) is False
    assert form_bool("0", default=True) is False
    assert form_bool("true", default=False) is True
