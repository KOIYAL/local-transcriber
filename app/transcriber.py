from __future__ import annotations

import gc
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import MODEL_PRESETS, Settings


ProgressCallback = Callable[[str, float, str], None]


class TranscriptionEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._models: dict[str, Any] = {}
        self._model_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _runtime(self, force_cpu: bool = False) -> tuple[str, str]:
        device = "cpu" if force_cpu else self.settings.device
        if device == "auto":
            try:
                import ctranslate2

                device = (
                    "cuda"
                    if ctranslate2.get_cuda_device_count() > 0
                    else "cpu"
                )
            except Exception:
                device = "cpu"

        compute_type = self.settings.compute_type
        if force_cpu:
            compute_type = "int8"
        elif compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        return device, compute_type

    def _model_source(self, model_name: str) -> tuple[str, bool]:
        if model_name == "local":
            if not self.settings.local_model:
                raise ValueError("No local model is configured.")
            if not self.settings.local_model.exists():
                raise ValueError(
                    f"The local model could not be found: {self.settings.local_model}"
                )
            return str(self.settings.local_model), True
        prepared_model = self.settings.model_dir / f"faster-whisper-{model_name}"
        if prepared_model.is_dir():
            return str(prepared_model), True
        if model_name not in MODEL_PRESETS:
            raise ValueError(f"Unsupported model: {model_name}")
        return model_name, False

    def _get_model(
        self,
        model_name: str,
        progress: ProgressCallback,
        *,
        force_cpu: bool = False,
    ) -> tuple[Any, str]:
        device, compute_type = self._runtime(force_cpu)
        cache_key = f"{model_name}:{device}:{compute_type}"
        with self._model_lock:
            if cache_key in self._models:
                return self._models[cache_key], device

            progress(
                "loading_model",
                0.08,
                "Loading the model. A download may be required the first time.",
            )
            from faster_whisper import WhisperModel

            source, local_only = self._model_source(model_name)
            self.settings.model_dir.mkdir(parents=True, exist_ok=True)
            model = WhisperModel(
                source,
                device=device,
                compute_type=compute_type,
                download_root=str(self.settings.model_dir),
                local_files_only=local_only,
            )
            self._models[cache_key] = model
            return model, device

    @staticmethod
    def _is_cuda_runtime_error(exc: RuntimeError) -> bool:
        message = str(exc).lower()
        markers = (
            "cuda",
            "cublas",
            "cudnn",
            "out of memory",
        )
        return any(marker in message for marker in markers)

    def _drop_cuda_model(self, model_name: str) -> None:
        with self._model_lock:
            keys = [
                key
                for key in self._models
                if key.startswith(f"{model_name}:cuda:")
            ]
            for key in keys:
                del self._models[key]
        gc.collect()

    def _transcribe_once(
        self,
        media_path: Path,
        options: dict[str, Any],
        progress: ProgressCallback,
        *,
        force_cpu: bool = False,
    ) -> dict[str, Any]:
        model, device = self._get_model(
            options["model"],
            progress,
            force_cpu=force_cpu,
        )
        progress("transcribing", 0.12, "Analyzing audio.")

        language = options.get("language") or None
        task = options.get("task", "transcribe")
        initial_prompt = options.get("initial_prompt") or None
        segments_iterator, info = model.transcribe(
            str(media_path),
            language=language,
            task=task,
            beam_size=int(options.get("beam_size", 5)),
            vad_filter=bool(options.get("vad_filter", True)),
            word_timestamps=False,
            initial_prompt=initial_prompt,
            condition_on_previous_text=True,
        )

        duration = max(float(getattr(info, "duration", 0.0) or 0.0), 0.001)
        segments: list[dict[str, Any]] = []
        for segment in segments_iterator:
            segments.append(
                {
                    "id": int(segment.id),
                    "start": round(float(segment.start), 3),
                    "end": round(float(segment.end), 3),
                    "text": segment.text.strip(),
                }
            )
            ratio = min(float(segment.end) / duration, 1.0)
            progress(
                "transcribing",
                0.12 + ratio * 0.78,
                f"Transcribing: {int(ratio * 100)}%",
            )

        text = " ".join(segment["text"] for segment in segments).strip()
        return {
            "text": text,
            "segments": segments,
            "language": getattr(info, "language", language or "unknown"),
            "language_probability": round(
                float(getattr(info, "language_probability", 0.0) or 0.0),
                4,
            ),
            "duration": round(duration, 3),
            "model": options["model"],
            "device": device,
            "task": task,
        }

    def transcribe(
        self,
        media_path: Path,
        options: dict[str, Any],
        progress: ProgressCallback,
    ) -> dict[str, Any]:
        with self._inference_lock:
            try:
                return self._transcribe_once(
                    media_path,
                    options,
                    progress,
                )
            except RuntimeError as exc:
                if (
                    self.settings.device != "auto"
                    or not self._is_cuda_runtime_error(exc)
                ):
                    raise
                self._drop_cuda_model(options["model"])
                progress(
                    "loading_model",
                    0.1,
                    "The GPU runtime is unavailable. Switching to the CPU.",
                )
                return self._transcribe_once(
                    media_path,
                    options,
                    progress,
                    force_cpu=True,
                )
