"""Discord Rich Presence (optional, privacy-safe, silent no-op without Discord).

Shows "Local Transcriber を使用中" style activity on the user's Discord profile
while the app runs. Design rules (ported from KOIYAL's godot-discord-presence):

- Never blocks or breaks the app: Discord absent / APP_ID empty / disabled
  -> every path is a no-op and no exception escapes this module.
- Write-only IPC + periodic reconnect: we never read responses. Discord sends
  one ~300B frame per command; with UPDATE_SEC=30 and RECONNECT_SEC=240 one
  connection cycle sends at most 8 frames (~2.4KB) which stays below the
  smallest pipe buffer (4KB), so we reconnect before the unread responses
  could clog the pipe. Keep these constants and this rationale together.
- Privacy: the activity never contains file names, transcript content, or any
  user data. Only a generic status and the app name are shown.
- Opt-out: set environment variable LT_DISCORD_PRESENCE=off (or 0/false/no).

Protocol: local IPC (Windows named pipe ``\\\\.\\pipe\\discord-ipc-N`` /
POSIX unix socket ``$XDG_RUNTIME_DIR|$TMPDIR|/tmp / discord-ipc-N``), frames
``[op:s32 LE][len:s32 LE][UTF-8 JSON]``; op=0 handshake, op=1 SET_ACTIVITY.
Activity timestamps are Unix seconds (discord-rpc C library convention).
"""

from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
from typing import Any, Callable

# HUMAN NEEDED: Discord Developer Portal で "Local Transcriber" 専用アプリを作成し
# Application ID をここへ（手順: docs/DISCORD-PRESENCE.md）。空の間は全体が no-op。
APP_ID = ""

UPDATE_SEC = 30.0
RECONNECT_SEC = 240.0
RETRY_SEC = 60.0

_ENV_FLAG = "LT_DISCORD_PRESENCE"


def presence_enabled_by_env() -> bool:
    value = os.getenv(_ENV_FLAG, "on").strip().lower()
    return value not in {"0", "off", "false", "no"}


def encode_frame(op: int, payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return struct.pack("<ii", op, len(body)) + body


def decode_frame(buf: bytes) -> dict[str, Any]:
    """For tests and potential future reads. Returns {} on malformed input."""
    if len(buf) < 8:
        return {}
    op, length = struct.unpack("<ii", buf[:8])
    if length < 0 or len(buf) < 8 + length:
        return {}
    try:
        payload = json.loads(buf[8 : 8 + length].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {"op": op, "payload": payload}


def build_activity(jobs: Any) -> dict[str, Any]:
    """Generic, privacy-safe activity from the JobManager state.

    ``jobs`` may be None or any object exposing ``list_recent()``; every
    failure falls back to the idle activity (this must never raise).
    """
    active = False
    try:
        if jobs is not None:
            recent = jobs.list_recent(20)
            active_statuses = {"queued", "loading_model", "transcribing", "finalizing"}
            for job in recent:
                if getattr(job, "status", "") in active_statuses:
                    active = True
                    break
                if getattr(job, "summary_status", "") in {"queued", "running"}:
                    active = True
                    break
    except Exception:
        active = False
    return {
        "details": "音声を文字起こし中" if active else "起動中",
        "state": "完全ローカル処理・外部送信なし",
        "timestamps": {"start": _START_UNIX},
        "assets": {"large_image": "logo", "large_text": "Local Transcriber"},
    }


_START_UNIX = int(time.time())


class _Connection:
    """One IPC connection (Windows named pipe or POSIX unix socket)."""

    def __init__(self, writer: Callable[[bytes], None], closer: Callable[[], None]):
        self._writer = writer
        self._closer = closer

    def write(self, data: bytes) -> bool:
        try:
            self._writer(data)
            return True
        except Exception:
            return False

    def close(self) -> None:
        try:
            self._closer()
        except Exception:
            pass


def _try_connect() -> _Connection | None:
    if os.name == "nt":
        for i in range(10):
            try:
                f = open(rf"\\.\pipe\discord-ipc-{i}", "r+b", buffering=0)
            except OSError:
                continue

            def _write(data: bytes, f=f) -> None:
                f.write(data)
                f.flush()

            return _Connection(_write, f.close)
        return None
    candidates = []
    for env in ("XDG_RUNTIME_DIR", "TMPDIR"):
        base = os.getenv(env)
        if base:
            candidates.append(base)
    candidates.append("/tmp")
    for base in candidates:
        for i in range(10):
            path = os.path.join(base, f"discord-ipc-{i}")
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect(path)
            except OSError:
                continue
            return _Connection(sock.sendall, sock.close)
    return None


class DiscordPresence:
    """Background presence updater. ``start()`` is safe to call unconditionally."""

    def __init__(
        self,
        activity_provider: Callable[[], dict[str, Any]],
        app_id: str = APP_ID,
        enabled: bool | None = None,
    ) -> None:
        self._provider = activity_provider
        self._app_id = app_id
        self._enabled = presence_enabled_by_env() if enabled is None else enabled
        self._exit = False
        self._thread: threading.Thread | None = None

    def _wanted(self) -> bool:
        return bool(self._app_id) and self._enabled and self._provider is not None

    def start(self) -> None:
        if self._thread is None and not self._exit and self._wanted():
            self._thread = threading.Thread(
                target=self._loop, name="discord-presence", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._exit = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    # --- worker thread ---------------------------------------------------

    def _sleep(self, sec: float) -> None:
        waited = 0.0
        while waited < sec and not self._exit:
            time.sleep(0.1)
            waited += 0.1

    def _loop(self) -> None:
        while not self._exit:
            if not self._wanted():
                self._sleep(RETRY_SEC)
                continue
            conn = _try_connect()
            if conn is None:
                self._sleep(RETRY_SEC)
                continue
            handshake = encode_frame(0, {"v": 1, "client_id": self._app_id})
            if not conn.write(handshake):
                conn.close()
                self._sleep(RETRY_SEC)
                continue
            connected_at = time.monotonic()
            while (
                not self._exit
                and self._wanted()
                and (time.monotonic() - connected_at) < RECONNECT_SEC
            ):
                try:
                    activity = self._provider()
                except Exception:
                    activity = {}
                if isinstance(activity, dict) and activity:
                    frame = encode_frame(
                        1,
                        {
                            "cmd": "SET_ACTIVITY",
                            "args": {"pid": os.getpid(), "activity": activity},
                            "nonce": str(time.monotonic_ns()),
                        },
                    )
                    if not conn.write(frame):
                        break
                self._sleep(UPDATE_SEC)
            conn.close()
