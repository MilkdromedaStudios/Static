"""Desktop boundary tests without Qt; frozen GUI/installer checks run on Windows CI."""

import os
import socket
import sys

import httpx
import pytest
from conftest import ScriptedProvider, new_chat, wait_run

from static_ai.bootstrap import ensure_local_model
from static_ai.config import Config
from static_ai.desktop.credentials import CredentialStore
from static_ai.desktop.runtime import LocalServer
from static_ai.desktop.state import (
    DesktopSettings,
    credential_names,
    instance_name,
    read_preferences,
    save_preferences,
)


class MemoryVault:
    def __init__(self):
        self.data = {}

    def get(self, target):
        return self.data.get(target)

    def set(self, target, secret):
        self.data[target] = secret

    def delete(self, target):
        self.data.pop(target, None)


def test_keys_stay_out_of_workspace_files_and_are_scoped(tmp_path, monkeypatch):
    monkeypatch.delenv("STATIC_DESKTOP_TEST_KEY", raising=False)
    vault = MemoryVault()
    first = CredentialStore(tmp_path / "one", vault)
    other = CredentialStore(tmp_path / "two", vault)
    first.save("STATIC_DESKTOP_TEST_KEY", "not-a-real-secret")
    assert first.get("STATIC_DESKTOP_TEST_KEY") == "not-a-real-secret"
    assert other.get("STATIC_DESKTOP_TEST_KEY") is None
    assert credential_names(first.root) == ["STATIC_DESKTOP_TEST_KEY"]
    assert all("not-a-real-secret" not in p.read_text() for p in tmp_path.rglob("*.json"))
    monkeypatch.delenv("STATIC_DESKTOP_TEST_KEY")
    first.load()
    assert os.getenv("STATIC_DESKTOP_TEST_KEY") == "not-a-real-secret"
    first.delete_all()
    assert first.get("STATIC_DESKTOP_TEST_KEY") is None
    assert os.getenv("STATIC_DESKTOP_TEST_KEY") is None
    assert credential_names(first.root) == []


def test_invalid_key_names_and_desktop_preferences(tmp_path):
    keys = CredentialStore(tmp_path, MemoryVault())
    with pytest.raises(ValueError, match="uppercase"):
        keys.save("../secret", "invalid")
    assert read_preferences(tmp_path).minimize_to_tray
    preferences = DesktopSettings(onboarded=True, minimize_to_tray=False, server_port=34567)
    save_preferences(tmp_path, preferences)
    assert read_preferences(tmp_path) == preferences
    assert instance_name(tmp_path) == instance_name(tmp_path / ".")
    assert instance_name(tmp_path) != instance_name(tmp_path / "other")


def test_desktop_server_auth_chat_and_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv("STATIC_AUTH_TOKEN", "prior-value")
    monkeypatch.setenv("STATIC_ALLOWED_HOSTS", "localhost")
    provider = ScriptedProvider()
    server = LocalServer(tmp_path, httpx.MockTransport(provider))
    server.start()
    port = server.socket.getsockname()[1]
    try:
        with httpx.Client(base_url=server.url, trust_env=False) as client:
            assert client.get("/api/settings").status_code == 401
            client.headers["Authorization"] = "Bearer " + server.token
            assert client.get("/api/health").json()["auth_enabled"]
            assert client.post("/api/conversations", json={}).status_code == 403
            client.headers["X-Static-Client"] = "web"
            conversation, run = new_chat(client, "Hello desktop")
            assert wait_run(client, run)["status"] == "completed"
            assert (
                client.get("/api/conversations/" + conversation).json()["messages"][-1]["content"]
                == "Done."
            )
            assert "Quick chat" in client.get("/mini.html").text
            assert server.token not in client.get("/assets/mini.js").text
    finally:
        server.stop()
    assert not server.thread.is_alive()
    with socket.socket() as connection:
        assert connection.connect_ex(("127.0.0.1", port)) != 0


def test_native_prompt_is_used_before_local_install(tmp_path, monkeypatch):
    config = Config(tmp_path)
    monkeypatch.setattr("static_ai.bootstrap._installed_models", lambda: None)
    monkeypatch.setattr("static_ai.bootstrap._ollama_binary", lambda: None)
    monkeypatch.setattr(
        "static_ai.bootstrap._install_ollama", lambda: pytest.fail("Installed without approval")
    )
    questions = []
    ensure_local_model(config, ask=lambda question: questions.append(question) or False)
    assert len(questions) == 1 and "Install Ollama" in questions[0]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Credential Manager integration")
def test_windows_credential_manager_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("STATIC_DESKTOP_TEST_KEY", raising=False)
    keys = CredentialStore(tmp_path)
    try:
        keys.save("STATIC_DESKTOP_TEST_KEY", "windows-ci-test-key")
        assert keys.get("STATIC_DESKTOP_TEST_KEY") == "windows-ci-test-key"
        assert "windows-ci-test-key" not in (tmp_path / "credential-names.json").read_text()
    finally:
        keys.delete_all()
    assert keys.get("STATIC_DESKTOP_TEST_KEY") is None
