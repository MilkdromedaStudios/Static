"""Regression tests for saved goals, portable actions and the Static migration."""

import json
import re
import sqlite3
from pathlib import Path

import httpx
import pytest
from conftest import ScriptedProvider, new_chat, wait_run
from fastapi.testclient import TestClient

from static_ai.app import create_app
from static_ai.bootstrap import ensure_local_model
from static_ai.config import Config, Model, Settings
from static_ai.db import Store, now


def test_saved_task_plan_and_reopen(workspace):
    client, app, provider = workspace
    task = client.post(
        "/api/tasks",
        json={
            "title": "Plan my launch",
            "objective": "Prepare a launch checklist",
            "category": "work",
        },
    ).json()
    provider.tool(
        "plan_update",
        {
            "steps": [
                {"title": "Write a brief", "status": "done"},
                {"title": "Review it", "status": "pending"},
            ]
        },
    )
    started = client.post("/api/tasks/" + task["id"] + "/start", json={})
    assert started.status_code == 202
    assert wait_run(client, started.json()["id"])["status"] == "completed"
    tasks = client.get("/api/tasks").json()
    assert tasks[0]["steps"][0]["status"] == "done"
    assert tasks[0]["run"]["status"] == "completed"
    assert client.get("/api/conversations").json()[0]["title"] == "Plan my launch"
    assert client.patch("/api/tasks/" + task["id"], json={"status": "done"}).status_code == 200
    assert client.post("/api/tasks/" + task["id"] + "/start", json={}).status_code == 409
    assert (
        client.patch(
            "/api/tasks/" + task["id"], json={"status": "open", "title": "Revised launch"}
        ).status_code
        == 200
    )
    assert client.post("/api/tasks", json={"title": " ", "objective": "Goal"}).status_code == 400
    assert (
        client.patch("/api/tasks/" + task["id"], json={"conversation_id": "other"}).status_code
        == 422
    )
    assert client.patch("/api/tasks/missing", json={"status": "done"}).status_code == 404


def test_calendar_export_timezone_and_escaping(workspace):
    client, app, provider = workspace
    provider.tool(
        "calendar_create",
        {
            "title": "Focus; one, two\nThree",
            "start": "2026-10-01T10:00:00+02:00",
            "end": "2026-10-01T11:00:00+02:00",
            "description": "é" * 160,
        },
    )
    conversation, run = new_chat(client, "Prepare a calendar file")
    assert wait_run(client, run)["status"] == "completed"
    artifact = client.get("/api/artifacts").json()[0]
    content = client.get("/api/artifacts/" + artifact["id"] + "/download").content
    assert b"DTSTART:20261001T080000Z" in content
    assert b"SUMMARY:Focus\\; one\\, two\\nThree" in content
    assert max(len(line) for line in content.split(b"\r\n")) <= 75
    assert "é" * 160 in content.decode().replace("\r\n ", "")
    provider.tool(
        "calendar_create",
        {"title": "Unknown timezone", "start": "2026-10-01T10:00:00", "end": "2026-10-01T11:00:00"},
    )
    _, run = new_chat(client)
    result = wait_run(client, run)
    assert any(e["kind"] == "tool_error" for e in result["events"])
    assert len(client.get("/api/artifacts").json()) == 1


def test_email_is_unsent_and_header_injection_is_rejected(workspace):
    client, app, provider = workspace
    provider.tool(
        "email_draft",
        {
            "subject": "Next steps",
            "to": "person@example.com",
            "body": "Hello,\nWhat works for you?",
        },
    )
    _, run = new_chat(client)
    wait_run(client, run)
    artifact = client.get("/api/artifacts").json()[0]
    content = client.get("/api/artifacts/" + artifact["id"] + "/download").text
    assert "X-Unsent: 1" in content
    assert "Subject: Next steps" in content
    provider.tool("email_draft", {"subject": "Hello\nBcc: hidden@example.com", "body": "Hello"})
    _, run = new_chat(client)
    assert any(e["kind"] == "tool_error" for e in wait_run(client, run)["events"])
    assert len(client.get("/api/artifacts").json()) == 1
    assert all("/chat/completions" in str(r.url) for r in provider.requests)


def test_csv_analysis_is_scoped_and_finite(workspace):
    client, app, provider = workspace
    conversation = client.post("/api/conversations", json={}).json()["id"]
    artifact = client.post(
        f"/api/conversations/{conversation}/upload",
        files={
            "file": ("budget.csv", b"Name,Cost\nOne,10\nTwo,20\nThree,NaN\nFour,text\n", "text/csv")
        },
    ).json()
    provider.tool("table_analyze", {"artifact_id": artifact["id"]})
    run = client.post(
        f"/api/conversations/{conversation}/chat", json={"message": "Analyze my CSV"}
    ).json()["id"]
    events = wait_run(client, run)["events"]
    result = next(e["data"]["result"] for e in events if e["kind"] == "tool_done")
    assert result["rows"] == 4
    assert result["columns"][1]["sum"] == 30
    assert result["columns"][1]["numeric"] == 2
    provider.tool("table_analyze", {"artifact_id": artifact["id"]})
    _, run = new_chat(client)
    assert any(e["kind"] == "tool_error" for e in wait_run(client, run)["events"])


def test_migration_keeps_chats_and_legacy_auth(tmp_path, monkeypatch):
    legacy = tmp_path / "buns.db"
    store = Store(legacy)
    store.execute("INSERT INTO conversations VALUES(?,?,?)", ("existing", "Keep me", now()))
    monkeypatch.setenv("BUNS_AUTH_TOKEN", "old-token-keeps-server-protected")
    monkeypatch.setenv("STATIC_ALLOWED_HOSTS", "testserver")
    monkeypatch.delenv("STATIC_AUTH_TOKEN", raising=False)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/conversations").status_code == 401
        client.headers["Authorization"] = "Bearer old-token-keeps-server-protected"
        assert client.get("/api/conversations").json()[0]["title"] == "Keep me"
    assert legacy.exists() and (tmp_path / "static.db").exists()
    with sqlite3.connect(legacy) as db:
        assert db.execute("SELECT title FROM conversations").fetchone()[0] == "Keep me"


def test_preferences_used_and_real_pages_served(workspace):
    client, app, provider = workspace
    settings = client.get("/api/settings").json()["settings"]
    settings["preferences"] = "Use metric units."
    settings["display_name"] = "Casey"
    assert client.put("/api/settings", json=settings).status_code == 200
    _, run = new_chat(client)
    wait_run(client, run)
    request = json.loads(provider.requests[-1].content)
    assert "Use metric units." in request["messages"][0]["content"]
    for page in [
        "index",
        "chat",
        "tasks",
        "create",
        "library",
        "skills",
        "connections",
        "settings",
    ]:
        response = client.get("/" + page + ".html")
        assert response.status_code == 200
        assert "./assets/static.svg" in response.text
    assert client.get("/missing.html").status_code == 404
    runtime = client.get("/assets/runtime.js").text
    assert re.search(r"mode:\s*[\'\"]live[\'\"]", runtime)
    assert len(client.get("/api/skills").json()) == 13


def test_preview_build_only_exports_public_assets(tmp_path):
    from scripts.build_preview import build

    output = build(tmp_path / "Static")
    assert "mode: 'preview'" in (output / "assets/runtime.js").read_text()
    assert (output / "tasks.html").exists()
    assert (output / ".nojekyll").exists()
    assert not list(output.rglob("*.py"))
    assert not list(output.rglob("*.db"))
    assert "static-preview-v2" in (output / "assets/demo.js").read_text()
    assert re.search(
        r"mode:\s*[\'\"]live[\'\"]",
        (Path(__file__).parents[1] / "static_ai/static/runtime.js").read_text(),
    )


def test_api_key_first_run_needs_no_ollama(tmp_path, monkeypatch):
    monkeypatch.setenv("STATIC_CHAT_MODEL", "tool-capable-model")
    monkeypatch.setenv("STATIC_CHAT_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("STATIC_CHAT_KEY_ENV", "STATIC_API_KEY")
    monkeypatch.setenv("STATIC_API_KEY", "not-a-real-secret")
    monkeypatch.setenv("STATIC_CHAT_PRICING_CONFIRMED", "true")
    monkeypatch.setenv("STATIC_CHAT_INPUT_PER_MILLION", "1.25")
    monkeypatch.setenv("STATIC_CHAT_OUTPUT_PER_MILLION", "2.5")
    config = Config(tmp_path)
    model = config.settings.models[0]
    assert not model.local and model.model == "tool-capable-model"
    assert model.key_env == "STATIC_API_KEY"
    assert model.input_per_million == 1.25
    monkeypatch.setattr(
        "static_ai.bootstrap._installed_models",
        lambda: (_ for _ in ()).throw(AssertionError("Tried Ollama")),
    )
    ensure_local_model(config)
    monkeypatch.delenv("STATIC_API_KEY")
    assert "not-a-real-secret" not in str(config.public())


def test_api_key_first_run_can_chat_without_ollama(tmp_path, monkeypatch):
    monkeypatch.setenv("STATIC_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("STATIC_CHAT_MODEL", "tool-capable-model")
    monkeypatch.setenv("STATIC_CHAT_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("STATIC_CHAT_PRICING_CONFIRMED", "true")
    monkeypatch.setenv("STATIC_API_KEY", "test-api-key")
    provider = ScriptedProvider()
    app = create_app(tmp_path, httpx.MockTransport(provider))
    with TestClient(app, headers={"X-Static-Client": "web"}) as client:
        _, run = new_chat(client, "Hello from the cloud profile")
        assert wait_run(client, run)["status"] == "completed"
        assert client.get("/api/settings").json()["keys"]["api"] is True
        assert "test-api-key" not in client.get("/api/settings").text
    request = next(r for r in provider.requests if r.url.path.endswith("/chat/completions"))
    assert str(request.url) == "https://api.example.com/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-api-key"
    assert json.loads(request.content)["model"] == "tool-capable-model"


def test_api_key_first_run_requires_pricing_and_key(tmp_path, monkeypatch):
    monkeypatch.setenv("STATIC_CHAT_MODEL", "model")
    monkeypatch.setenv("STATIC_CHAT_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("STATIC_CHAT_KEY_ENV", "STATIC_API_KEY")
    monkeypatch.setenv("STATIC_API_KEY", "example")
    monkeypatch.delenv("STATIC_CHAT_PRICING_CONFIRMED", raising=False)
    with pytest.raises(ValueError, match="Confirm current provider pricing"):
        Config(tmp_path)
    monkeypatch.setenv("STATIC_CHAT_PRICING_CONFIRMED", "true")
    monkeypatch.delenv("STATIC_API_KEY")
    with pytest.raises(ValueError, match="Set STATIC_API_KEY"):
        Config(tmp_path)


def test_missing_ollama_requires_interactive_install_and_server_still_starts(tmp_path, monkeypatch):
    config = Config(tmp_path)
    monkeypatch.setattr("static_ai.bootstrap._installed_models", lambda: None)
    monkeypatch.setattr("static_ai.bootstrap.shutil.which", lambda _: None)
    monkeypatch.setattr("static_ai.bootstrap._ask", lambda _: False)
    monkeypatch.setattr(
        "static_ai.bootstrap._install_ollama",
        lambda: (_ for _ in ()).throw(AssertionError("Unexpected install")),
    )
    ensure_local_model(config)


def test_installed_ollama_autostarts_only_for_its_local_endpoint(tmp_path, monkeypatch):
    config = Config(tmp_path)
    models = iter([None, {"qwen3:4b"}])
    monkeypatch.setattr("static_ai.bootstrap._installed_models", lambda: next(models))
    monkeypatch.setattr("static_ai.bootstrap.shutil.which", lambda _: "/usr/bin/ollama")
    started = []
    monkeypatch.setattr(
        "static_ai.bootstrap._launch_ollama",
        lambda path, root: started.append((path, root)) or True,
    )
    ensure_local_model(config)
    assert started == [("/usr/bin/ollama", tmp_path.resolve())]
    config.settings = Settings(
        models=[
            Model(id="local", name="LM Studio", model="local", base_url="http://localhost:1234/v1")
        ]
    )
    ensure_local_model(config)
    assert len(started) == 1
