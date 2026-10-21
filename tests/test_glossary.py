from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.mark.parametrize("recording", [False, True])
@pytest.mark.parametrize(
    "glossary,expected",
    [(None, ""), ("  \n ", ""), ("  KOIYAL、人名\n製品名  ", "KOIYAL、人名\n製品名"),
     ("  " + "用語" * 300 + "  ", "用語" * 250)],
)
def test_glossary_reaches_job_options(tmp_path, monkeypatch, recording, glossary, expected):
    settings = replace(
        main.SETTINGS, data_dir=tmp_path, upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs", model_dir=tmp_path / "models",
    )
    monkeypatch.setattr(main, "SETTINGS", settings)
    submitted = {}

    class FakeJob:
        def as_dict(self):
            return {"id": "fake-job"}

    def submit(filename, path, options):
        submitted.update(options)
        return FakeJob()

    with TestClient(main.app, base_url="http://127.0.0.1") as client:
        main.app.state.models.status = lambda: {"ready": True, "model": "tiny"}
        main.app.state.jobs.submit = submit
        main.app.state.recorder.submit_job = submit
        data = {} if glossary is None else {"glossary": glossary}
        if recording:
            sid = client.post("/api/recording/start").json()["session_id"]
            client.post(f"/api/recording/{sid}/chunk", content=b"fake audio")
            response = client.post(f"/api/recording/{sid}/stop", data=data)
        else:
            response = client.post(
                "/api/jobs", files={"file": ("test.wav", b"fake audio", "audio/wav")},
                data=data,
            )
        assert response.status_code == 202
        assert submitted["initial_prompt"] == expected
        assert submitted["vad_filter"] is True
        assert submitted["model"] == "tiny"
