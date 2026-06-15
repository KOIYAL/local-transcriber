from pathlib import Path

from app.exporters import (
    format_timestamp,
    to_srt,
    to_txt,
    to_vtt,
    write_exports,
)


SEGMENTS = [
    {"id": 0, "start": 0.0, "end": 1.25, "text": " 最初の文です。 "},
    {"id": 1, "start": 61.1, "end": 63.456, "text": "Second line."},
]


def test_format_timestamp() -> None:
    assert format_timestamp(3661.234) == "01:01:01,234"
    assert format_timestamp(61.1, ".") == "00:01:01.100"


def test_text_exports() -> None:
    assert to_txt(SEGMENTS) == "最初の文です。\nSecond line.\n"
    assert "00:00:00,000 --> 00:00:01,250" in to_srt(SEGMENTS)
    assert to_vtt(SEGMENTS).startswith("WEBVTT\n\n00:00:00.000")


def test_write_exports(tmp_path: Path) -> None:
    files = write_exports(
        tmp_path,
        metadata={"filename": "sample.mp3", "language": "ja"},
        segments=SEGMENTS,
    )
    assert set(files) == {"txt", "srt", "vtt", "json"}
    assert all(path.exists() for path in files.values())
    assert '"language": "ja"' in files["json"].read_text(encoding="utf-8")
