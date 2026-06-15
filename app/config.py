from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    upload_dir: Path
    output_dir: Path
    model_dir: Path
    max_upload_bytes: int
    keep_uploads: bool
    device: str
    compute_type: str
    local_model: Path | None
    max_workers: int


def load_settings() -> Settings:
    data_dir = _env_path("TRANSCRIBER_DATA_DIR", PROJECT_ROOT / "data")
    local_model_value = os.getenv("WHISPER_LOCAL_MODEL", "").strip()
    local_model = None
    if local_model_value:
        candidate = Path(local_model_value).expanduser()
        local_model = candidate if candidate.is_absolute() else PROJECT_ROOT / candidate

    return Settings(
        data_dir=data_dir,
        upload_dir=data_dir / "uploads",
        output_dir=data_dir / "outputs",
        model_dir=_env_path("WHISPER_MODEL_DIR", data_dir / "models"),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "2048")) * 1024 * 1024,
        keep_uploads=_env_bool("KEEP_UPLOADS"),
        device=os.getenv("WHISPER_DEVICE", "auto").strip().lower(),
        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "auto").strip().lower(),
        local_model=local_model,
        max_workers=max(1, int(os.getenv("TRANSCRIBER_WORKERS", "1"))),
    )


SETTINGS = load_settings()

MODEL_PRESETS = {
    "tiny": {
        "label": "Tiny",
        "description": "最速。短いメモや動作確認向け",
    },
    "base": {
        "label": "Base",
        "description": "軽量。CPUでの簡易利用向け",
    },
    "small": {
        "label": "Small",
        "description": "速度と精度のバランスが良い推奨設定",
    },
    "medium": {
        "label": "Medium",
        "description": "高精度。CPUでは時間がかかります",
    },
    "large-v3": {
        "label": "Large v3",
        "description": "最高精度。GPU推奨",
    },
    "turbo": {
        "label": "Turbo",
        "description": "高精度かつ高速。GPU推奨",
    },
}

ALLOWED_EXTENSIONS = {
    ".aac",
    ".avi",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
    ".wma",
}
