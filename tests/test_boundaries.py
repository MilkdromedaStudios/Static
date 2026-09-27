import asyncio
import socket
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from conftest import new_chat, wait_run
from fastapi.testclient import TestClient
from pydantic import ValidationError

from buns.app import create_app
from buns.config import Model, Settings
from buns.db import Store, now
from buns.network import fetch_public, public_address


def test_cost_gate_blocks_before_paid_request(workspace):
    client, app, provider = workspace
    app.state.config.settings.models = [
        Model(
            id="paid",
            name="Paid",
            model="example",
            base_url="https://example.com/v1",
            local=False,
            pricing_confirmed=True,
            input_per_million=100,
            output_per_million=100,
        )
    ]
    _, run = new_chat(client, budget_usd=0)
    result = wait_run(client, run)
    assert result["status"] == "failed" and "Spending limit" in result["error"]
    assert len(provider.requests) == 0


def test_router_prefers_cheapest_and_respects_local_mode(workspace):
    client, app, provider = workspace
    providers = app.state.engine.providers
    app.state.config.settings.models.append(
        Model(
            id="paid",
            name="Paid",
            model="test",
            base_url="https://example.com/v1",
            local=False,
            pricing_confirmed=True,
            input_per_million=1,
            output_per_million=1,
        )
    )
    assert providers.choose("coordinator").id == "local"
    assert providers.choose("coordinator", "local").local


def test_atomic_reservations_cannot_race(tmp_path):
    db = Store(tmp_path / "db.sqlite")
    db.execute(
        "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
        ("run", "conv", "running", "economy", 1, "{}", "", now(), now()),
    )

    def reserve(_):
        try:
            db.reserve("run", 0.6, "test", 1)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(reserve, [1, 2])) == 1
    assert db.spending("run") == 0.6


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost",
        "http://127.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]",
        "https://user:password@example.com",
        "https://example.com:8443",
    ],
)
async def test_blocks_private_or_unsafe_urls(url):
    with pytest.raises(ValueError):
        await public_address(url)


async def test_dns_pinning_and_redirect_validation(monkeypatch):
    loop = asyncio.get_running_loop()

    async def lookup(host, port, type):
        ip = "127.0.0.1" if host == "private.example" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(loop, "getaddrinfo", lookup)
    seen = []

    def handle(request):
        seen.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["Host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        return httpx.Response(302, headers={"Location": "http://private.example/secret"})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "buns.network.httpx.AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handle)),
    )
    with pytest.raises(ValueError, match="Private"):
        await fetch_public("https://example.com")
    assert len(seen) == 1


def test_cors_auth_and_download_boundaries(tmp_path, monkeypatch):
    monkeypatch.setenv("BUNS_AUTH_TOKEN", "a-long-test-token-for-private-workspace")
    monkeypatch.setenv("BUNS_ALLOWED_HOSTS", "testserver")
    app = create_app(tmp_path)
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
        assert c.get("/api/conversations").status_code == 401
        auth = {"Authorization": "Bearer a-long-test-token-for-private-workspace"}
        assert c.get("/api/conversations", headers=auth).status_code == 200
        assert c.post("/api/conversations", headers=auth, json={}).status_code == 403
        headers = {**auth, "X-Buns-Client": "web", "Origin": "https://evil.example"}
        assert c.post("/api/conversations", headers=headers, json={}).status_code == 403
        assert c.get("/api/health", headers={**auth, "Host": "evil.example"}).status_code == 400
        assert "script-src 'self'" in c.get("/").headers["content-security-policy"]


def test_settings_are_validated_and_never_expose_env(workspace, monkeypatch):
    client, app, provider = workspace
    monkeypatch.setenv("MY_SECRET", "do-not-echo-this")
    s = client.get("/api/settings").json()["settings"]
    s["models"][0]["key_env"] = "MY_SECRET"
    assert client.put("/api/settings", json=s).status_code == 200
    assert "do-not-echo-this" not in client.get("/api/settings").text
    s["models"][0]["base_url"] = "file:///etc"
    assert client.put("/api/settings", json=s).status_code == 422
    with pytest.raises(ValidationError):
        Settings(daily_budget_usd=float("nan"))


def test_server_restart_interrupts_ambiguous_work(tmp_path, monkeypatch):
    monkeypatch.setenv("BUNS_ALLOWED_HOSTS", "testserver")
    app = create_app(tmp_path)
    app.state.store.execute(
        "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
        ("run", "conv", "running", "economy", 1, "{}", "", now(), now()),
    )
    with TestClient(app) as client:
        data = client.get("/api/runs/run").json()
        assert data["status"] == "interrupted"
        assert "Server restarted" in data["error"]


def test_upload_size_and_extension_rejected(workspace):
    client, app, provider = workspace
    conv = client.post("/api/conversations", json={}).json()["id"]
    assert (
        client.post(
            f"/api/conversations/{conv}/upload", files={"file": ("evil.exe", b"hello")}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/conversations/{conv}/upload", files={"file": ("big.txt", b"x" * 5_000_001)}
        ).status_code
        == 413
    )


async def test_search_cache_avoids_duplicate_fetches(workspace, monkeypatch):
    from buns.skills.base import Context
    from buns.skills.web import Search, search

    client, app, provider = workspace
    calls = []

    async def fetch(url):
        calls.append(url)
        return (
            url,
            b'<div class="result"><a class="result__a" href="https://example.com">Example</a><div class="result__snippet">Facts</div></div>',
            "text/html",
        )

    monkeypatch.setattr("buns.skills.web.fetch_public", fetch)
    engine = app.state.engine
    ctx = Context(
        "run",
        "conv",
        "local",
        engine.store,
        engine.config,
        engine.providers,
        engine.artifacts,
        engine.media,
    )
    first = await search(ctx, Search(query="example"))
    second = await search(ctx, Search(query="example"))
    assert len(calls) == 1 and second["cached"] and first["untrusted_web_content"]


def test_model_outage_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setenv("BUNS_ALLOWED_HOSTS", "testserver")

    def fail(request):
        raise httpx.ConnectError("offline")

    app = create_app(tmp_path, httpx.MockTransport(fail))
    with TestClient(app, headers={"X-Buns-Client": "web"}) as c:
        _, run = new_chat(c)
        result = wait_run(c, run)
        assert result["status"] == "failed" and "Start Ollama" in result["error"]
        assert c.post("/api/models/local/test").json()["ok"] is False
