import pytest

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
    with TestClient(app, base_url="http://127.0.0.1") as client:
        app.state.models = FakeManager("small", "medium")
        payload = client.get("/api/models/upgrade-check").json()
        assert payload == {
            "current": "small",
            "recommended": "medium",
            "upgrade_available": True,
        }


def test_upgrade_starts_download_when_available() -> None:
    with TestClient(app, base_url="http://127.0.0.1") as client:
        manager = FakeManager("small", "medium")
        app.state.models = manager
        response = client.post("/api/models/upgrade")
        assert response.status_code == 202
        assert response.json()["model"] == "medium"
        assert manager.upgraded


def test_upgrade_conflicts_when_already_best() -> None:
    with TestClient(app, base_url="http://127.0.0.1") as client:
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
    manager.memory_bytes = 64 * 1024**3  # recommends turbo
    check = manager.upgrade_check()
    assert check == {
        "current": "tiny",
        "recommended": "turbo",
        "upgrade_available": True,
    }

    manager.model_name = "medium"
    assert manager.upgrade_check()["upgrade_available"] is True

    manager.model_name = "turbo"
    check = manager.upgrade_check()
    assert check["upgrade_available"] is False


def _install_fake_model(model_dir, name: str) -> None:
    folder = model_dir / f"faster-whisper-{name}"
    folder.mkdir(parents=True)
    for filename in ("config.json", "model.bin", "tokenizer.json"):
        (folder / filename).write_bytes(b"x")


@pytest.mark.parametrize("installed", ["tiny", "medium"])
def test_installed_model_is_kept_and_upgrade_is_offered(tmp_path, monkeypatch, installed) -> None:
    from app import model_manager as mm
    from app.config import Settings

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
    monkeypatch.setattr(mm, "total_memory_bytes", lambda: 64 * 1024**3)  # -> turbo
    _install_fake_model(settings.model_dir, installed)

    manager = mm.ModelManager(settings)
    # The downloaded model wins at startup (no silent re-download) ...
    assert manager.model_name == installed
    assert manager.status()["ready"] is True
    # ... and the manual check now has something to offer.
    assert manager.upgrade_check() == {
        "current": installed,
        "recommended": "turbo",
        "upgrade_available": True,
    }

    # Nothing installed: the recommendation is used directly.
    fresh = Settings(**{**settings.__dict__, "model_dir": tmp_path / "empty"})
    assert mm.ModelManager(fresh).model_name == "turbo"
