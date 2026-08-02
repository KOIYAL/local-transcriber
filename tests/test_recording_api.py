from fastapi.testclient import TestClient

from app.main import app


class FakeJob:
    def as_dict(self) -> dict:
        return {"id": "job-xyz", "status": "queued"}


def _force_setup(ready: bool) -> None:
    app.state.models.status = lambda: {"ready": ready, "model": "tiny"}


def test_recording_start_requires_setup() -> None:
    with TestClient(app) as client:
        _force_setup(False)
        response = client.post("/api/recording/start")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "setup_incomplete"


def test_recording_full_flow() -> None:
    with TestClient(app) as client:
        _force_setup(True)
        submitted = {}

        def fake_submit(filename, path, options):
            submitted["filename"] = filename
            submitted["bytes"] = path.read_bytes()
            submitted["options"] = options
            path.unlink(missing_ok=True)
            return FakeJob()

        app.state.recorder.submit_job = fake_submit

        assert client.get("/api/recording/status").json() == {"state": "idle"}

        response = client.post("/api/recording/start")
        assert response.status_code == 201
        sid = response.json()["session_id"]

        response = client.post(
            f"/api/recording/{sid}/chunk",
            content=b"chunk-1",
            headers={"X-Audio-Level": "0.42"},
        )
        assert response.status_code == 200
        assert response.json()["bytes_written"] == 7

        assert client.post(f"/api/recording/{sid}/pause").json()["state"] == "paused"
        assert (
            client.post(f"/api/recording/{sid}/resume").json()["state"] == "recording"
        )

        response = client.post(f"/api/recording/{sid}/stop")
        assert response.status_code == 202
        assert response.json()["id"] == "job-xyz"
        assert submitted["bytes"] == b"chunk-1"
        assert submitted["options"]["model"] == "tiny"
        assert submitted["filename"].startswith("recording-")

        assert client.get("/api/recording/status").json() == {"state": "idle"}


def test_recording_double_start_conflicts_and_cancel_cleans_up() -> None:
    with TestClient(app) as client:
        _force_setup(True)
        sid = client.post("/api/recording/start").json()["session_id"]
        response = client.post("/api/recording/start")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "recording_in_progress"

        assert client.delete(f"/api/recording/{sid}").status_code == 204
        assert client.get("/api/recording/status").json() == {"state": "idle"}

        response = client.post(f"/api/recording/{sid}/chunk", content=b"late")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "recording_not_found"
