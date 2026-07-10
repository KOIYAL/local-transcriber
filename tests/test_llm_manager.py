"""LlmManager drives the modelshelf CLI; these tests fake the binary."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from app import llm_manager
from app.llm_manager import APP_ID, RECOMMEND_REF, LlmManager


class FakeCompleted:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def make_runner(table: dict[tuple[str, ...], Any], calls: list[list[str]]):
    """A subprocess.run stand-in keyed by the exact CLI arguments."""

    def run(argv: list[str], **_kwargs) -> FakeCompleted:
        args = argv[1:]
        calls.append(args)
        if args[:2] == ["refs", "add"]:
            return FakeCompleted(stdout="")
        response = table.get(tuple(args))
        if response is None:
            return FakeCompleted(returncode=1, stderr=f"unexpected args: {args}")
        if isinstance(response, str):
            return FakeCompleted(stdout=response)
        return FakeCompleted(stdout=json.dumps(response))

    return run


def test_bundled_binary_is_found_in_frozen_builds(tmp_path, monkeypatch) -> None:
    # Packaged desktop builds ship modelshelf next to the backend
    # executable (desktop/backend.spec); resolution must find it there.
    name = "modelshelf.exe" if os.name == "nt" else "modelshelf"
    bundled = tmp_path / name
    bundled.write_bytes(b"")
    monkeypatch.delenv("MODELSHELF_BIN", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "local-transcriber-backend"))
    assert llm_manager._default_binary() == str(bundled)


def test_without_binary_the_feature_is_unavailable() -> None:
    manager = LlmManager(binary=None)
    status = manager.status()
    assert status["available"] is False
    assert status["status"] == "unavailable"
    manager.start()  # must be a harmless no-op
    assert manager.status()["status"] == "unavailable"
    assert manager.model_path() is None


def test_adopts_previously_provisioned_model_offline(tmp_path) -> None:
    model_file = tmp_path / "blobs" / "sha256-abc"
    model_file.parent.mkdir(parents=True)
    model_file.write_bytes(b"GGUF")
    calls: list[list[str]] = []
    runner = make_runner(
        {
            ("list", "--json"): [
                {
                    "id": "sha256:abc",
                    "display_name": "Adopted Model",
                    "refs": [{"app_id": RECOMMEND_REF, "alias": "qwen3-4b"}],
                },
                {"id": "sha256:other", "display_name": "Unrelated", "refs": []},
            ],
            ("path", "sha256:abc"): str(model_file),
        },
        calls,
    )

    manager = LlmManager(binary="modelshelf-fake", runner=runner)
    status = manager.status()
    assert status["ready"] is True
    assert status["model"] == "Adopted Model"
    assert manager.model_path() == model_file


def test_provision_downloads_and_registers_the_ref(tmp_path) -> None:
    model_file = tmp_path / "blobs" / "sha256-abc"
    model_file.parent.mkdir(parents=True)
    model_file.write_bytes(b"GGUF")
    calls: list[list[str]] = []
    runner = make_runner(
        {
            ("list", "--json"): [],
            ("recommend", "--task", "chat", "--json"): {
                "best": "qwen3-4b",
                "upgrade": None,
                "items": [
                    {
                        "entry": {
                            "name": "qwen3-4b",
                            "file_bytes": 4,
                            "extra_files": [],
                        }
                    }
                ],
            },
            ("path",): str(tmp_path),
            ("recommend", "--task", "chat", "--pull", "--json"): {
                "model": {"id": "sha256:abc", "display_name": "Qwen3 4B"},
                "path": str(model_file),
                "extras": [],
                "replaced": [],
                "removed": [],
            },
        },
        calls,
    )

    manager = LlmManager(binary="modelshelf-fake", runner=runner)
    assert manager.status()["status"] == "not_started"
    manager._provision()  # run synchronously; start() would thread this

    status = manager.status()
    assert status["ready"] is True, status
    assert status["model"] == "Qwen3 4B"
    assert manager.model_path() == model_file
    refs_calls = [c for c in calls if c[:2] == ["refs", "add"]]
    assert refs_calls == [
        ["refs", "add", "sha256:abc", "--app", APP_ID, "--alias", "summary-model"]
    ]


def test_provision_failure_is_reported_not_raised(tmp_path) -> None:
    calls: list[list[str]] = []
    runner = make_runner(
        {
            ("list", "--json"): [],
            ("recommend", "--task", "chat", "--json"): {"best": None, "items": []},
            ("path",): str(tmp_path),
            # No entry for the --pull invocation: it fails with exit code 1.
        },
        calls,
    )

    manager = LlmManager(binary="modelshelf-fake", runner=runner)
    manager._provision()
    status = manager.status()
    assert status["status"] == "failed"
    assert status["ready"] is False
    assert "could not be prepared" in status["message"]
