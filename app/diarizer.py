"""Optional, offline CPU speaker diarization with explicit model setup."""
from __future__ import annotations

import hashlib
import importlib
import shutil
import tarfile
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.system_info import total_memory_bytes


@dataclass(frozen=True)
class ModelAsset:
    url: str
    size: int
    sha256: str
    filename: str
    model_size: int
    model_sha256: str
    member: str | None = None


# Verified against the official release assets on 2026-10-21.
BASE_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
ASSETS = (
    ModelAsset(
        f"{BASE_URL}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
        6_958_444, "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488",
        "segmentation.onnx", 5_992_913,
        "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079",
        "sherpa-onnx-pyannote-segmentation-3-0/model.onnx",
    ),
    ModelAsset(
        f"{BASE_URL}/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx",
        39_593_761, "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
        "embedding.onnx", 39_593_761,
        "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b",
    ),
)


def availability_reason() -> str:
    try:
        if total_memory_bytes() < 8 * 1024**3:
            return "memory_below_8gb"
    except (OSError, ValueError):
        return "memory_unknown"
    try:
        module = importlib.import_module("sherpa_onnx")
        if not hasattr(module, "OfflineSpeakerDiarization"):
            return "sherpa_onnx_unavailable"
    except (ImportError, OSError):
        return "sherpa_onnx_unavailable"
    return ""


def _verified(path: Path, size: int, digest: str) -> bool:
    try:
        if path.stat().st_size != size:
            return False
        checksum = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                checksum.update(chunk)
        return checksum.hexdigest() == digest
    except OSError:
        return False


def download_asset(asset: ModelAsset, path: Path, progress: Callable[[int], None]) -> None:
    # Only fixed public model URLs are requested; no user data is attached.
    with urllib.request.urlopen(asset.url, timeout=30) as response, path.open("wb") as output:
        received = 0
        while chunk := response.read(1024 * 1024):
            received += len(chunk)
            if received > asset.size:
                raise ValueError("Unexpected model download size")
            output.write(chunk)
            progress(received)


def create_engine(segmentation: Path, embedding: Path):
    import sherpa_onnx as sherpa

    config = sherpa.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(segmentation)),
            num_threads=2, provider="cpu",
        ),
        embedding=sherpa.SpeakerEmbeddingExtractorConfig(
            model=str(embedding), num_threads=2, provider="cpu",
        ),
        clustering=sherpa.FastClusteringConfig(num_clusters=-1, threshold=0.5),
        min_duration_on=0.3, min_duration_off=0.5,
    )
    if not config.validate():
        raise RuntimeError("Invalid speaker diarization configuration")
    return sherpa.OfflineSpeakerDiarization(config)


def decode_mono(path: Path):
    from faster_whisper.audio import decode_audio

    return decode_audio(str(path), sampling_rate=16000)


class Diarizer:
    def __init__(self, model_dir: Path, *, availability=availability_reason,
                 downloader=download_asset, engine_factory=create_engine,
                 decoder=decode_mono, assets=ASSETS):
        self.directory = model_dir / "diarization"
        self.assets = assets
        self._reason = availability()
        self._downloader = downloader
        self._engine_factory = engine_factory
        self._decoder = decoder
        self._lock = threading.Lock()
        self._inference_lock = threading.Lock()
        self._thread = None
        ready = not self._reason and all(
            _verified(self.directory / a.filename, a.model_size, a.model_sha256) for a in assets
        )
        self._status = "unavailable" if self._reason else "ready" if ready else "not_started"
        self._progress = 1.0 if ready else 0.0

    def status(self) -> dict:
        with self._lock:
            return {"available": not self._reason, "ready": self._status == "ready",
                    "reason": self._reason, "status": self._status,
                    "progress": round(self._progress, 3),
                    "download_bytes": sum(a.size for a in self.assets)}

    def start(self) -> None:
        with self._lock:
            if self._reason or self._status in {"ready", "downloading"}:
                return
            self._status, self._progress = "downloading", 0.0
            self._thread = threading.Thread(target=self._provision, daemon=True,
                                            name="diarization-model-setup")
            self._thread.start()

    def _set_progress(self, fraction: float) -> None:
        with self._lock:
            self._progress = min(0.99, max(0.0, fraction))

    def _provision(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            total = sum(a.size for a in self.assets)
            done = 0
            for asset in self.assets:
                target = self.directory / asset.filename
                if not _verified(target, asset.model_size, asset.model_sha256):
                    partial = target.with_suffix(".download")
                    staging = target.with_suffix(".part")
                    try:
                        self._downloader(asset, partial, lambda n: self._set_progress((done + n) / total))
                        if not _verified(partial, asset.size, asset.sha256):
                            raise ValueError("Model download checksum mismatch")
                        if asset.member:
                            # Copy only the known regular member; never extract arbitrary paths/links.
                            with tarfile.open(partial, "r:bz2") as archive:
                                member = archive.getmember(asset.member)
                                if not member.isfile() or member.size != asset.model_size:
                                    raise ValueError("Unexpected segmentation archive member")
                                with archive.extractfile(member) as source, staging.open("wb") as output:
                                    shutil.copyfileobj(source, output)
                        else:
                            partial.replace(staging)
                        if not _verified(staging, asset.model_size, asset.model_sha256):
                            raise ValueError("Model checksum mismatch")
                        staging.replace(target)
                    finally:
                        partial.unlink(missing_ok=True)
                        staging.unlink(missing_ok=True)
                done += asset.size
                self._set_progress(done / total)
            with self._lock:
                self._status, self._progress = "ready", 1.0
        except Exception:
            with self._lock:
                self._status = "failed"

    def diarize(self, path: Path, progress: Callable[[float], None]) -> list[dict]:
        if not self.status()["ready"]:
            raise RuntimeError("Speaker diarization models are not ready")
        # Release the engine after each job and serialize optional CPU inference.
        with self._inference_lock:
            engine = self._engine_factory(*(self.directory / a.filename for a in self.assets))
            if engine.sample_rate != 16000:
                raise RuntimeError("Unsupported speaker diarization sample rate")
            samples = self._decoder(path)
            if len(samples) == 0:
                return []

            def callback(processed, total):
                progress(processed / max(total, 1))
                return 0

            result = engine.process(samples, callback=callback).sort_by_start_time()
            return [{"start": float(s.start), "end": float(s.end), "speaker": int(s.speaker)}
                    for s in result]


def assign_speakers(segments: list[dict], turns: list[dict]) -> list[dict]:
    """Use total overlap per speaker; ties go to the first speaker heard.

    Uncovered segments stay unlabeled rather than inventing a speaker.
    Numbering restarts for each recording and is independent of cluster IDs.
    """
    turns = sorted(turns, key=lambda turn: turn["start"])
    labels = {}
    for turn in turns:
        labels.setdefault(turn["speaker"], f"話者{len(labels) + 1}")
    assigned = []
    for segment in segments:
        overlaps = dict.fromkeys(labels, 0.0)
        for turn in turns:
            overlaps[turn["speaker"]] += max(
                0.0, min(segment["end"], turn["end"]) - max(segment["start"], turn["start"])
            )
        copy = dict(segment)
        if overlaps:
            speaker = max(overlaps, key=overlaps.get)
            if overlaps[speaker] > 0:
                copy["speaker"] = labels[speaker]
        assigned.append(copy)
    return assigned
