from dataclasses import dataclass

from app.discord_presence import (
    DiscordPresence,
    build_activity,
    decode_frame,
    encode_frame,
)


def test_frame_roundtrip() -> None:
    frame = encode_frame(1, {"cmd": "SET_ACTIVITY", "nonce": "42"})
    decoded = decode_frame(frame)
    assert decoded["op"] == 1
    assert decoded["payload"]["cmd"] == "SET_ACTIVITY"


def test_frame_multibyte_length_is_bytes() -> None:
    frame = encode_frame(1, {"details": "音声を文字起こし中"})
    decoded = decode_frame(frame)
    assert decoded["payload"]["details"] == "音声を文字起こし中"
    # length header counts UTF-8 bytes, not characters
    import struct

    _, length = struct.unpack("<ii", frame[:8])
    assert length == len(frame) - 8


def test_decode_rejects_malformed() -> None:
    assert decode_frame(b"") == {}
    assert decode_frame(b"\x01\x02\x03") == {}
    import struct

    assert decode_frame(struct.pack("<ii", 1, -5)) == {}
    assert decode_frame(struct.pack("<ii", 1, 4) + b"abcd") == {}
    assert decode_frame(struct.pack("<ii", 1, 4) + b'"s"\n') == {}  # non-dict JSON


@dataclass
class _FakeJob:
    status: str = "completed"
    summary_status: str = "none"


class _FakeJobs:
    def __init__(self, jobs: list[_FakeJob]):
        self._jobs = jobs

    def list_recent(self, limit: int = 20) -> list[_FakeJob]:
        return self._jobs[:limit]


class _BrokenJobs:
    def list_recent(self, limit: int = 20):
        raise RuntimeError("boom")


def test_build_activity_idle_and_active() -> None:
    idle = build_activity(None)
    assert idle["details"] == "起動中"
    assert "timestamps" in idle and "assets" in idle

    active = build_activity(_FakeJobs([_FakeJob(status="transcribing")]))
    assert active["details"] == "音声を文字起こし中"

    summary = build_activity(_FakeJobs([_FakeJob(summary_status="running")]))
    assert summary["details"] == "音声を文字起こし中"

    done = build_activity(_FakeJobs([_FakeJob(status="completed")]))
    assert done["details"] == "起動中"


def test_build_activity_never_raises() -> None:
    assert build_activity(_BrokenJobs())["details"] == "起動中"


def test_build_activity_contains_no_user_data() -> None:
    activity = build_activity(_FakeJobs([_FakeJob(status="transcribing")]))
    flat = str(activity)
    assert ".mp3" not in flat and ".wav" not in flat  # ファイル名を載せない設計の回帰ガード


def test_noop_without_app_id() -> None:
    presence = DiscordPresence(activity_provider=lambda: {}, app_id="")
    presence.start()
    assert presence._thread is None  # 空APP_ID -> スレッド起動しない
    presence.stop()  # 例外を出さない


def test_noop_when_disabled() -> None:
    presence = DiscordPresence(
        activity_provider=lambda: {}, app_id="000000000000000000", enabled=False
    )
    presence.start()
    assert presence._thread is None
    presence.stop()


def test_env_flag(monkeypatch) -> None:
    from app import discord_presence as dp

    monkeypatch.setenv("LT_DISCORD_PRESENCE", "off")
    assert dp.presence_enabled_by_env() is False
    monkeypatch.setenv("LT_DISCORD_PRESENCE", "on")
    assert dp.presence_enabled_by_env() is True
    monkeypatch.delenv("LT_DISCORD_PRESENCE")
    assert dp.presence_enabled_by_env() is True
