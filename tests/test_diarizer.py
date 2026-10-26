"""All network, model decoding and native inference use small fakes."""
import hashlib
import io
import multiprocessing
import os
import tarfile
import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import diarizer, main
from app.diarizer import Diarizer, ModelAsset, assign_speakers
from app.exporters import to_srt, to_txt, to_vtt, write_exports


def fake_assets():
    model = b"segmentation"
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:bz2") as archive:
        info = tarfile.TarInfo("models/model.onnx")
        info.size = len(model)
        archive.addfile(info, io.BytesIO(model))
    archive_data = stream.getvalue()
    embedding = b"embedding"
    sha = lambda data: hashlib.sha256(data).hexdigest()
    assets = (
        ModelAsset("https://example.invalid/seg", len(archive_data), sha(archive_data),
                   "segmentation.onnx", len(model), sha(model), "models/model.onnx"),
        ModelAsset("https://example.invalid/emb", len(embedding), sha(embedding),
                   "embedding.onnx", len(embedding), sha(embedding)),
    )
    payloads = {assets[0].url: archive_data, assets[1].url: embedding}
    return assets, payloads


def fake_manager(tmp_path, **kwargs):
    assets, payloads = fake_assets()
    calls = []

    def download(asset, path, progress):
        calls.append(asset.url)
        path.write_bytes(payloads[asset.url])
        progress(len(payloads[asset.url]))

    manager = Diarizer(tmp_path, availability=lambda: "", assets=assets,
                      downloader=kwargs.pop("downloader", download), **kwargs)
    return manager, calls


def test_setup_opt_in_progress_integrity_and_offline_reuse(tmp_path):
    manager, calls = fake_manager(tmp_path)
    assert manager.status()["status"] == "not_started"
    assert calls == []
    manager.start()
    manager._thread.join(3)
    assert manager.status()["ready"]
    assert manager.status()["progress"] == 1
    assert len(calls) == 2
    manager.start()
    assert len(calls) == 2
    offline, calls = fake_manager(tmp_path)
    assert offline.status()["ready"]
    assert calls == []
    (manager.directory / "embedding.onnx").write_bytes(b"x" * 9)
    corrupt, calls = fake_manager(tmp_path)
    assert not corrupt.status()["ready"]
    corrupt._provision()
    assert corrupt.status()["ready"]
    assert calls == [corrupt.assets[1].url]


def test_failed_download_is_retryable_and_removes_partial_files(tmp_path):
    def broken(asset, path, progress):
        path.write_bytes(b"wrong download")
        progress(5)

    manager, _ = fake_manager(tmp_path, downloader=broken)
    manager.start()
    manager._thread.join(3)
    assert manager.status()["status"] == "failed"
    assert not list(manager.directory.iterdir())
    good, calls = fake_manager(tmp_path)
    manager._downloader = good._downloader
    manager.start()
    manager._thread.join(3)
    assert manager.status()["ready"]
    assert len(calls) == 2


def test_setup_is_single_flight(tmp_path):
    entered, release = threading.Event(), threading.Event()
    good, calls = fake_manager(tmp_path)

    def blocked(*args):
        entered.set()
        assert release.wait(3)
        good._downloader(*args)

    manager, _ = fake_manager(tmp_path, downloader=blocked)
    manager.start()
    assert entered.wait(3)
    thread = manager._thread
    manager.start()
    assert manager._thread is thread
    assert manager.status()["status"] == "downloading"
    release.set()
    thread.join(3)
    assert len(calls) == 2


@pytest.mark.parametrize("reason", ["memory_below_8gb", "sherpa_onnx_unavailable", "memory_unknown"])
def test_unavailable_never_downloads(tmp_path, reason):
    manager = Diarizer(tmp_path, availability=lambda: reason,
                      downloader=lambda *args: pytest.fail("unexpected network"))
    manager.start()
    assert manager.status()["available"] is False
    assert manager.status()["ready"] is False
    assert manager.status()["reason"] == reason


def test_availability_checks_memory_and_native_import(monkeypatch):
    monkeypatch.setattr(diarizer, "total_memory_bytes", lambda: 8 * 1024**3 - 1)
    monkeypatch.setattr(diarizer.importlib, "import_module", lambda _: pytest.fail("unexpected import"))
    assert diarizer.availability_reason() == "memory_below_8gb"
    monkeypatch.setattr(diarizer, "total_memory_bytes", lambda: 8 * 1024**3)
    monkeypatch.setattr(diarizer.importlib, "import_module", lambda _: SimpleNamespace(OfflineSpeakerDiarization=True))
    assert diarizer.availability_reason() == ""

    def broken(_):
        raise OSError("native library missing")
    monkeypatch.setattr(diarizer.importlib, "import_module", broken)
    assert diarizer.availability_reason() == "sherpa_onnx_unavailable"


def test_native_adapter_and_decode_use_fakes(tmp_path):
    progress = []
    paths = []

    class Engine:
        sample_rate = 16000

        def process(self, samples, callback):
            assert samples == [0.25, -0.25]
            assert callback(1, 2) == 0
            return SimpleNamespace(sort_by_start_time=lambda: [SimpleNamespace(start=0, end=1.2, speaker=7)])

    def factory(seg, emb):
        assert seg.name == "segmentation.onnx" and emb.name == "embedding.onnx"
        return Engine()

    def decode(path):
        paths.append(path)
        return [0.25, -0.25]

    path = tmp_path / "meeting.wav"
    assert diarizer.infer_speakers(
        path, (tmp_path / "segmentation.onnx", tmp_path / "embedding.onnx"),
        progress.append, engine_factory=factory, decoder=decode,
    ) == [{"start": 0.0, "end": 1.2, "speaker": 7}]
    assert paths == [path]
    assert progress == [0.5]


def fake_process_worker(path, model_paths, progress):
    assert [p.name for p in model_paths] == ["segmentation.onnx", "embedding.onnx"]
    assert multiprocessing.get_start_method() == "spawn"
    progress(0.25)
    progress(0.75)
    return [{"start": 0.0, "end": 1.2, "speaker": os.getpid()}]


def failing_process_worker(path, model_paths, progress):
    raise RuntimeError("fake native error")


def crashing_process_worker(path, model_paths, progress):
    os._exit(7)


def hanging_process_worker(path, model_paths, progress):
    progress(0.1)
    time.sleep(60)


def test_inference_spawns_and_returns_progress_without_native_dependencies(tmp_path):
    manager, _ = fake_manager(tmp_path, worker=fake_process_worker)
    manager._provision()
    progress = []
    parent_pid = os.getpid()
    previous = {p.pid for p in multiprocessing.active_children()}
    result = manager.diarize(tmp_path / "meeting.wav", progress.append)
    assert result[0]["speaker"] != parent_pid
    assert progress == [0.25, 0.75]
    assert {p.pid for p in multiprocessing.active_children()} == previous


@pytest.mark.parametrize("worker,error", [
    (failing_process_worker, "failed"), (crashing_process_worker, "exited"),
    (hanging_process_worker, "timed out"),
])
def test_child_failure_and_timeout_are_reaped_and_allow_retry(tmp_path, worker, error):
    manager, _ = fake_manager(tmp_path, worker=worker, timeout=2)
    manager._provision()
    previous = {p.pid for p in multiprocessing.active_children()}
    with pytest.raises((RuntimeError, TimeoutError), match=error):
        manager.diarize(tmp_path / "meeting.wav", lambda _: None)
    assert {p.pid for p in multiprocessing.active_children()} == previous
    manager._worker = fake_process_worker
    manager._timeout = 10
    assert manager.diarize(tmp_path / "meeting.wav", lambda _: None)


def test_decode_audio_contract(monkeypatch, tmp_path):
    import faster_whisper.audio
    calls = []
    monkeypatch.setattr(faster_whisper.audio, "decode_audio", lambda *args, **kwargs: calls.append((args, kwargs)))
    diarizer.decode_mono(tmp_path / "meeting.mp4")
    assert calls == [((str(tmp_path / "meeting.mp4"),), {"sampling_rate": 16000})]


def test_assignment_aggregates_overlap_ties_and_uncovered_segments():
    turns = [{"start": 0, "end": 1, "speaker": 7},
             {"start": 1, "end": 2.5, "speaker": 2},
             {"start": 2.5, "end": 4, "speaker": 7}]
    segments = [{"start": 0, "end": 4, "text": "a"},
                {"start": 1, "end": 2, "text": "b"},
                {"start": 0, "end": 2, "text": "tie"},
                {"start": 4, "end": 5, "text": "gap"},
                {"start": 1, "end": 1, "text": "zero"}]
    result = assign_speakers(segments, list(reversed(turns)))
    assert [s.get("speaker") for s in result] == ["話者1", "話者2", "話者1", None, None]
    assert all("speaker" not in s for s in segments)
    assert assign_speakers(segments, []) == segments


def test_export_speaker_changes_and_json(tmp_path):
    import json
    segments = [{"start": i, "end": i + 1, "text": f" line{i} ", **({"speaker": s} if s else {})}
                for i, s in enumerate(["話者1", "話者1", "話者2", None, "話者2"])]
    assert to_txt(segments) == "話者1: line0\nline1\n話者2: line2\nline3\n話者2: line4\n"
    for export in [to_srt, to_vtt]:
        text = export(segments)
        assert text.count("話者1: ") == 1
        assert text.count("話者2: ") == 2
        assert "\nline1\n" in text
    files = write_exports(tmp_path, metadata={"language": "ja"}, segments=segments)
    assert json.loads(files["json"].read_text(encoding="utf-8"))["segments"] == segments


@pytest.mark.parametrize("recording", [False, True])
@pytest.mark.parametrize("enabled,ready", [(False, False), (True, False), (True, True)])
def test_api_options_and_setup_gate(tmp_path, monkeypatch, recording, enabled, ready):
    settings = replace(main.SETTINGS, data_dir=tmp_path, upload_dir=tmp_path / "uploads",
                       output_dir=tmp_path / "outputs", model_dir=tmp_path / "models")
    monkeypatch.setattr(main, "SETTINGS", settings)
    fake, calls = fake_manager(tmp_path)
    monkeypatch.setattr(main, "Diarizer", lambda _: fake)
    submitted = {}

    def submit(filename, path, options):
        submitted.update(options)
        return SimpleNamespace(as_dict=lambda: {"id": "fake"})

    with TestClient(main.app, base_url="http://127.0.0.1") as client:
        assert not client.get("/api/config").json()["diarize"]["ready"]
        assert not client.get("/api/diarize/setup").json()["ready"]
        assert calls == []
        if ready:
            assert client.post("/api/diarize/setup").status_code == 202
            fake._thread.join(3)
            assert client.get("/api/config").json()["diarize"]["ready"]
        main.app.state.models.status = lambda: {"ready": True, "model": "tiny"}
        main.app.state.jobs.submit = submit
        main.app.state.recorder.submit_job = submit
        data = {"diarize": "true"} if enabled else {}
        if recording:
            sid = client.post("/api/recording/start").json()["session_id"]
            client.post(f"/api/recording/{sid}/chunk", content=b"fake audio")
            response = client.post(f"/api/recording/{sid}/stop", data=data)
        else:
            response = client.post("/api/jobs", files={"file": ("test.wav", b"fake audio")}, data=data)
        if enabled and not ready and not recording:
            assert response.status_code == 409
            assert not submitted
            assert not list(settings.upload_dir.iterdir())
        else:
            assert response.status_code == 202
            assert submitted["diarize"] == enabled


def test_download_stream_uses_only_asset_url_and_bounds_size(tmp_path, monkeypatch):
    assets, payloads = fake_assets()
    asset = assets[1]
    calls, progress = [], []

    def open_url(url, timeout):
        calls.append((url, timeout))
        return io.BytesIO(payloads[url])

    monkeypatch.setattr(diarizer.urllib.request, "urlopen", open_url)
    target = tmp_path / "download"
    diarizer.download_asset(asset, target, progress.append)
    assert calls == [(asset.url, 30)]
    assert target.read_bytes() == b"embedding"
    assert progress[-1] == asset.size
    payloads[asset.url] = b"x" * (asset.size + 1)
    with pytest.raises(ValueError, match="size"):
        diarizer.download_asset(asset, target, progress.append)


def test_archive_rejects_links_even_with_expected_archive_hash(tmp_path):
    assets, payloads = fake_assets()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:bz2") as archive:
        info = tarfile.TarInfo(assets[0].member)
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        archive.addfile(info)
    data = stream.getvalue()
    unsafe = replace(assets[0], size=len(data), sha256=hashlib.sha256(data).hexdigest())

    def download(asset, path, progress):
        path.write_bytes(data)

    manager = Diarizer(tmp_path, availability=lambda: "", assets=(unsafe, assets[1]), downloader=download)
    manager._provision()
    assert manager.status()["status"] == "failed"
    assert not list(manager.directory.iterdir())
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("seconds,maximum,expected", [
    (None, 3600, 3600), (0, 3600, 120), (10, 3600, 120),
    (20, 3600, 120), (60, 3600, 240), (1000, 3600, 3060),
    (1200, 3600, 3600), (7200, 3600, 3600),
    (None, 2, 2), (1, 2, 2),
])
def test_timeout_scales_with_audio_and_preserves_configured_ceiling(tmp_path, seconds, maximum, expected):
    manager, _ = fake_manager(tmp_path, timeout=maximum)
    assert manager._timeout_for_audio(seconds) == expected


def test_diarize_uses_audio_timeout_for_deadline(tmp_path, monkeypatch):
    manager, _ = fake_manager(tmp_path, worker=hanging_process_worker, timeout=10)
    manager._provision()
    durations = []

    def timeout_for_audio(seconds):
        durations.append(seconds)
        return 0.01

    monkeypatch.setattr(manager, "_timeout_for_audio", timeout_for_audio)
    with pytest.raises(TimeoutError):
        manager.diarize(tmp_path / "meeting.wav", lambda _: None, audio_seconds=45)
    assert durations == [45]
