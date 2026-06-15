from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def format_timestamp(seconds: float, separator: str = ",") -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def to_txt(segments: list[dict[str, Any]]) -> str:
    return "\n".join(segment["text"].strip() for segment in segments).strip() + "\n"


def to_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = format_timestamp(float(segment["start"]))
        end = format_timestamp(float(segment["end"]))
        blocks.append(f"{index}\n{start} --> {end}\n{segment['text'].strip()}")
    return "\n\n".join(blocks) + "\n"


def to_vtt(segments: list[dict[str, Any]]) -> str:
    blocks = ["WEBVTT"]
    for segment in segments:
        start = format_timestamp(float(segment["start"]), ".")
        end = format_timestamp(float(segment["end"]), ".")
        blocks.append(f"{start} --> {end}\n{segment['text'].strip()}")
    return "\n\n".join(blocks) + "\n"


def write_exports(
    output_dir: Path,
    *,
    metadata: dict[str, Any],
    segments: list[dict[str, Any]],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "txt": output_dir / "transcript.txt",
        "srt": output_dir / "transcript.srt",
        "vtt": output_dir / "transcript.vtt",
        "json": output_dir / "transcript.json",
    }
    files["txt"].write_text(to_txt(segments), encoding="utf-8")
    files["srt"].write_text(to_srt(segments), encoding="utf-8")
    files["vtt"].write_text(to_vtt(segments), encoding="utf-8")
    files["json"].write_text(
        json.dumps(
            {**metadata, "segments": segments},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return files
