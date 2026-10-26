from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path


RELEASE_API = "https://api.github.com/repos/KOIYAL/local-transcriber/releases/latest"
RELEASE_URL = "https://github.com/KOIYAL/local-transcriber/releases/tag/"
CACHE_SECONDS = 24 * 60 * 60


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A check makes exactly one request, even if GitHub redirects.
        return None


def fetch_latest_release() -> dict:
    request = urllib.request.Request(
        RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Local-Transcriber"},
    )
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=5) as response:
        return json.loads(response.read(1024 * 1024))


def _version(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"v?\d{1,6}\.\d{1,6}\.\d{1,6}", value):
        raise ValueError("Unsupported release version")
    return tuple(int(part) for part in value.removeprefix("v").split("."))


def _release(data: dict) -> dict:
    tag = data["tag_name"]
    _version(tag)
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("Not a stable release")
    # Only link to this project's stable releases, including when reading cache.
    if data["html_url"] != RELEASE_URL + tag:
        raise ValueError("Unexpected release URL")
    return {"tag_name": tag, "html_url": data["html_url"]}


class UpdateChecker:
    def __init__(
        self,
        data_dir: Path,
        fetcher: Callable[[], dict] = fetch_latest_release,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = data_dir / "update-check.json"
        self.fetcher = fetcher
        self.clock = clock
        self._lock = threading.Lock()
        self._cache: dict | None = None

    def _read_cache(self, now: float) -> dict | None:
        try:
            entry = self._cache
            if entry is None:
                entry = json.loads(self.path.read_text(encoding="utf-8"))
            if not 0 <= now - entry["checked_at"] < CACHE_SECONDS:
                return None
            if entry["release"] is not None:
                _release(entry["release"])
            return entry
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def check(self, current: str, force: bool = False) -> dict:
        result = {
            "current": current, "latest": None, "url": None,
            "update_available": False, "checked": False,
        }
        if os.getenv("LT_UPDATE_CHECK", "").strip().lower() in {"off", "0", "false", "no"}:
            return result
        with self._lock:
            now = self.clock()
            entry = None if force else self._read_cache(now)
            if entry is None:
                try:
                    release = _release(self.fetcher())
                except Exception:
                    # Offline, rate-limited or malformed responses are non-fatal.
                    release = None
                entry = {"checked_at": now, "release": release}
                self._cache = entry
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self.path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(entry), encoding="utf-8")
                    temporary.replace(self.path)
                except OSError:
                    # Keep the in-memory cache even on read-only/full disks.
                    pass
            release = entry["release"]
            if release is not None:
                try:
                    newer = _version(release["tag_name"]) > _version(current)
                except ValueError:
                    return result
                result.update(
                    latest=release["tag_name"].removeprefix("v"),
                    url=release["html_url"], update_available=newer, checked=True,
                )
        return result
