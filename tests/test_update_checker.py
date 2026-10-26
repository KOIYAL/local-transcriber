import io
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import update_checker as uc
from app.main import app


def release(tag="v0.7.1"):
    return {"tag_name": tag, "html_url": uc.RELEASE_URL + tag}


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    monkeypatch.delenv("LT_UPDATE_CHECK", raising=False)

    def unexpected(*args, **kwargs):
        pytest.fail("Real network access is forbidden")

    monkeypatch.setattr(uc.urllib.request, "build_opener", unexpected)


def test_transport_uses_one_fixed_request_and_timeout(monkeypatch):
    calls = []

    class FakeOpener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            return io.BytesIO(json.dumps(release()).encode())

    def build(handler):
        assert isinstance(handler, uc._NoRedirect)
        assert handler.redirect_request(None, None, 302, "", {}, "https://example.com") is None
        return FakeOpener()

    monkeypatch.setattr(uc.urllib.request, "build_opener", build)
    assert uc.fetch_latest_release() == release()
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.full_url == uc.RELEASE_API
    assert request.data is None
    assert request.get_method() == "GET"
    assert timeout == 5


@pytest.mark.parametrize("current,tag,newer", [
    ("0.6.0", "v0.7.1", True), ("0.7.1", "v0.7.1", False),
    ("0.10.0", "v0.9.0", False), ("0.9.0", "0.10.0", True),
])
def test_versions(tmp_path, current, tag, newer):
    assert uc.UpdateChecker(tmp_path, lambda: release(tag)).check(current) == {
        "current": current, "latest": tag.removeprefix("v"),
        "url": uc.RELEASE_URL + tag, "update_available": newer, "checked": True,
    }


def test_cache_expires_and_recomputes_current_after_restart(tmp_path):
    calls = []
    now = [1000.0]

    def fetch():
        calls.append(True)
        return release()

    checker = uc.UpdateChecker(tmp_path, fetch, lambda: now[0])
    assert checker.check("0.6.0")["update_available"]
    checker = uc.UpdateChecker(tmp_path, fetch, lambda: now[0])
    assert not checker.check("0.7.1")["update_available"]
    now[0] += uc.CACHE_SECONDS - 1
    checker.check("0.6.0")
    assert len(calls) == 1
    now[0] += 1
    checker.check("0.6.0")
    assert len(calls) == 2


@pytest.mark.parametrize("flag", ["off", "0", "false", "no", " OFF "])
def test_disabled_ignores_even_cached_update(tmp_path, monkeypatch, flag):
    checker = uc.UpdateChecker(tmp_path, release)
    checker.check("0.6.0")
    monkeypatch.setenv("LT_UPDATE_CHECK", flag)
    checker.fetcher = lambda: pytest.fail("Disabled check must not fetch")
    result = checker.check("0.6.0")
    assert not result["checked"]
    assert not result["update_available"]
    assert result["url"] is None


def test_failure_is_silent_and_cached_across_restart(tmp_path):
    calls = []

    def fail():
        calls.append(True)
        raise TimeoutError()

    for _ in range(2):
        result = uc.UpdateChecker(tmp_path, fail).check("0.6.0")
        assert not result["checked"]
        assert not result["update_available"]
    assert len(calls) == 1


@pytest.mark.parametrize("data", [
    {}, [], {**release(), "tag_name": "v0.8.0-rc.1"},
    {**release(), "prerelease": True}, {**release(), "draft": True},
    {**release(), "html_url": "javascript:alert(1)"},
    {**release(), "html_url": "https://github.com.evil/KOIYAL/local-transcriber"},
])
def test_invalid_release_is_hidden(tmp_path, data):
    assert not uc.UpdateChecker(tmp_path, lambda: data).check("0.6.0")["checked"]


@pytest.mark.parametrize("contents", ["{", "[]", '{"checked_at": "bad"}'])
def test_broken_cache_is_replaced(tmp_path, contents):
    (tmp_path / "update-check.json").write_text(contents)
    assert uc.UpdateChecker(tmp_path, release).check("0.6.0")["checked"]


def test_unwritable_cache_uses_memory(tmp_path):
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    calls = []

    def fetch():
        calls.append(True)
        return release()

    checker = uc.UpdateChecker(blocked, fetch)
    assert checker.check("0.6.0")["checked"]
    assert checker.check("0.6.0")["checked"]
    assert len(calls) == 1


def test_concurrent_checks_share_one_request(tmp_path):
    calls = []

    def fetch():
        calls.append(True)
        return release()

    checker = uc.UpdateChecker(tmp_path, fetch)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(checker.check, ["0.6.0"] * 8))
    assert all(r["checked"] for r in results)
    assert len(calls) == 1


def test_api_uses_actual_app_version(tmp_path):
    with TestClient(app, base_url="http://127.0.0.1") as client:
        app.state.update_checker = uc.UpdateChecker(tmp_path, lambda: release("v0.7.3"))
        response = client.get("/api/update-check")
        assert response.status_code == 200
        assert response.json()["current"] == app.version == "0.7.2"
        assert response.json()["update_available"]


@pytest.mark.parametrize("restart", [False, True])
def test_force_bypasses_memory_and_disk_cache_and_persists_result(tmp_path, restart):
    calls = []

    def fetch():
        calls.append(True)
        return release("v0.7.1" if len(calls) == 1 else "v0.7.3")

    checker = uc.UpdateChecker(tmp_path, fetch)
    assert checker.check("0.7.2")["latest"] == "0.7.1"
    if restart:
        checker = uc.UpdateChecker(tmp_path, fetch)
    assert checker.check("0.7.2")["latest"] == "0.7.1"
    assert len(calls) == 1
    assert checker.check("0.7.2", force=True)["latest"] == "0.7.3"
    assert len(calls) == 2
    assert checker.check("0.7.2")["latest"] == "0.7.3"
    assert uc.UpdateChecker(tmp_path, lambda: pytest.fail("must use cache")).check("0.7.2")["latest"] == "0.7.3"


def test_force_respects_disabled_check_and_replaces_failed_cache(tmp_path, monkeypatch):
    def offline():
        raise TimeoutError()

    checker = uc.UpdateChecker(tmp_path, offline)
    assert not checker.check("0.7.2")["checked"]
    checker.fetcher = lambda: release("v0.7.3")
    assert not checker.check("0.7.2")["checked"]
    assert checker.check("0.7.2", force=True)["checked"]
    checker.fetcher = lambda: pytest.fail("disabled must not fetch")
    monkeypatch.setenv("LT_UPDATE_CHECK", "off")
    assert not checker.check("0.7.2", force=True)["checked"]


def test_force_failure_is_cached(tmp_path):
    checker = uc.UpdateChecker(tmp_path, release)
    assert checker.check("0.6.0")["checked"]

    def offline():
        raise TimeoutError()

    checker.fetcher = offline
    assert not checker.check("0.6.0", force=True)["checked"]
    assert not uc.UpdateChecker(tmp_path, lambda: pytest.fail("must use cached failure")).check("0.6.0")["checked"]


def test_api_force_parameter_bypasses_cache(tmp_path):
    calls = []

    def fetch():
        calls.append(True)
        return release()

    with TestClient(app, base_url="http://127.0.0.1") as client:
        app.state.update_checker = uc.UpdateChecker(tmp_path, fetch)
        for query in ("", "?force=false", "?force=true"):
            assert client.get("/api/update-check" + query).status_code == 200
        assert len(calls) == 2
        assert client.get("/api/update-check?force=invalid").status_code == 422
        assert len(calls) == 2
