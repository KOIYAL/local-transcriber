from fastapi.testclient import TestClient

from app.main import app


class FakeManager:
    def __init__(self, current: str, recommended: str) -> None:
        self.current = current
        self.recommended = recommended
        self.upgraded = False

    def upgrade_check(self) -> dict:
        return {
            "current": self.current,
            "recommended": self.recommended,
            "upgrade_available": self.current != self.recommended,
        }

    def upgrade_to_recommended(self) -> dict:
        if self.current == self.recommended:
            raise ValueError("no_upgrade_available")
        self.upgraded = True
        return {"status": "downloading", "model": self.recommended}


def test_upgrade_check_reports_available() -> None:
    with TestClient(app) as client:
        app.state.models = FakeManager("small", "medium")
        payload = client.get("/api/models/upgrade-check").json()
        assert payload == {
            "current": "small",
            "recommended": "medium",
            "upgrade_available": True,
        }


def test_upgrade_starts_download_when_available() -> None:
    with TestClient(app) as client:
        manager = FakeManager("small", "medium")
        app.state.models = manager
        response = client.post("/api/models/upgrade")
        assert response.status_code == 202
        assert response.json()["model"] == "medium"
        assert manager.upgraded


def test_upgrade_conflicts_when_already_best() -> None:
    with TestClient(app) as client:
        app.state.models = FakeManager("medium", "medium")
        response = client.post("/api/models/upgrade")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "no_upgrade_available"


def test_manager_upgrade_check_ordering(tmp_path) -> None:
    from app.config import Settings
    from app.model_manager import ModelManager

    settings = Settings(
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        model_dir=tmp_path / "models",
        max_upload_bytes=1024,
        keep_uploads=False,
        device="cpu",
        compute_type="int8",
        local_model=None,
        max_workers=1,
    )
    manager = ModelManager(settings)
    manager.model_name = "tiny"
    manager.memory_bytes = 64 * 1024**3  # recommends medium
    check = manager.upgrade_check()
    assert check == {
        "current": "tiny",
        "recommended": "medium",
        "upgrade_available": True,
    }

    manager.model_name = "medium"
    check = manager.upgrade_check()
    assert check["upgrade_available"] is False
