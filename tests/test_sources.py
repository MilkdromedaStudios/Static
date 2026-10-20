"""Other AI sources: the Anthropic Messages API, Claude Code and MCP tool servers."""

import json
import os
import stat
import sys
import time
from pathlib import Path

import httpx
import pytest
from conftest import ScriptedProvider, new_chat, wait_run
from fastapi.testclient import TestClient
from pydantic import ValidationError

from static_ai.app import create_app
from static_ai.config import Model

ROOT = Path(__file__).parent
posix_only = pytest.mark.skipif(os.name == "nt", reason="fake executables use a shebang")


def cloud(**kwargs):
    return {
        "id": "claude",
        "name": "Claude",
        "local": False,
        "pricing_confirmed": True,
        "input_per_million": 3,
        "output_per_million": 15,
        **kwargs,
    }


def use_models(client, *models):
    settings = client.get("/api/settings").json()["settings"]
    settings["models"] = list(models)
    response = client.put("/api/settings", json=settings)
    assert response.status_code == 200, response.text


def events(result, kind):
    return [e["data"] for e in result["events"] if e["kind"] == kind]


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("STATIC_ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")
    monkeypatch.delenv("STATIC_AUTH_TOKEN", raising=False)
    clients = []

    def make(handler):
        app = create_app(tmp_path, httpx.MockTransport(handler))
        client = TestClient(app, headers={"X-Static-Client": "web"})
        clients.append(client.__enter__())
        return client, app

    yield make
    for client in clients:
        client.__exit__(None, None, None)


# --- Anthropic Messages API ---------------------------------------------------------------


class AnthropicFake:
    def __init__(self):
        self.requests, self.replies = [], []

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "claude-test-1-20260101"}]})
        if request.url.path == "/v1/messages":
            content = self.replies.pop(0) if self.replies else [{"type": "text", "text": "Done."}]
            return httpx.Response(
                200,
                json={
                    "content": content,
                    "usage": {
                        "input_tokens": 1000,
                        "cache_read_input_tokens": 1000,
                        "output_tokens": 100,
                    },
                },
            )
        return httpx.Response(404)


def test_anthropic_source_translates_tools_and_settles_costs(make_app, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_TEST_KEY", "sk-ant-test-secret")
    fake = AnthropicFake()
    client, app = make_app(fake)
    use_models(
        client,
        cloud(
            provider="anthropic",
            model="claude-test-1",
            base_url="https://api.anthropic.com/v1",
            key_env="ANTHROPIC_TEST_KEY",
        ),
    )
    fake.replies.append(
        [
            {"type": "text", "text": "Planning first."},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "plan_update",
                "input": {"steps": [{"title": "Draft", "status": "active"}]},
            },
        ]
    )
    conv, run = new_chat(client, "Plan my week")
    result = wait_run(client, run)
    assert result["status"] == "completed", result
    assert events(result, "plan")
    first, second = [json.loads(r.content) for r in fake.requests]
    request = fake.requests[0]
    assert request.headers["x-api-key"] == "sk-ant-test-secret"
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in request.headers
    assert "You are Static" in first["system"]
    assert first["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "Plan my week"}]}
    ]
    plan = next(t for t in first["tools"] if t["name"] == "plan_update")
    assert plan["input_schema"]["properties"]["steps"]
    assert second["messages"][1]["content"][1]["type"] == "tool_use"
    result_block = second["messages"][2]["content"][0]
    assert result_block["type"] == "tool_result" and result_block["tool_use_id"] == "toolu_1"
    messages = client.get("/api/conversations/" + conv).json()["messages"]
    assert messages[-1]["content"] == "Done."
    # Two calls of (1000 + 1000 cached) input and 100 output tokens at 3 / 15 USD per million.
    assert app.state.store.spending(run) == pytest.approx(2 * (2000 * 3 + 100 * 15) / 1e6)
    assert "sk-ant-test-secret" not in client.get("/api/settings").text


def test_anthropic_health_accepts_model_aliases(make_app, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_TEST_KEY", "sk-ant-test-secret")
    fake = AnthropicFake()
    client, app = make_app(fake)
    use_models(
        client,
        cloud(
            provider="anthropic",
            model="claude-test-1",
            base_url="https://api.anthropic.com/v1",
            key_env="ANTHROPIC_TEST_KEY",
        ),
    )
    response = client.post("/api/models/claude/test").json()
    assert response["ok"] and response["message"] == "Connected"
    assert fake.requests[-1].url.params["limit"] == "1000"


# --- Claude Code --------------------------------------------------------------------------

FAKE_CLAUDE = """#!{python}
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Claude Code)")
    sys.exit(0)
if args == ["auth", "status"]:
    print(json.dumps({{"loggedIn": True}}))
    sys.exit(0)
prompt = sys.stdin.read()
system = open(args[args.index("--system-prompt-file") + 1], encoding="utf-8").read()
with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({{"args": args, "prompt": prompt, "system": system,
        "cwd_files": os.listdir("."), "env": sorted(os.environ),
        "api_key": os.environ.get("ANTHROPIC_API_KEY")}}) + "\\n")
usage = {{"input_tokens": 10, "cache_creation_input_tokens": 990, "output_tokens": 100}}
if os.environ.get("FAKE_CLAUDE_MODE") == "logged_out":
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": True,
        "result": "Not logged in · Please run /login"}}))
    sys.exit(1)
if "--json-schema" not in args:
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
        "result": "Specialist text", "usage": usage}}))
elif '"role": "tool"' in prompt:
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "",
        "structured_output": {{"message": "All done.", "tool_calls": []}}, "usage": usage}}))
else:
    call = {{"name": "plan_update", "arguments": {{"steps": [{{"title": "Draft"}}]}}}}
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "",
        "structured_output": {{"message": "", "tool_calls": [call]}}, "usage": usage}}))
"""


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    path = tmp_path / "bin" / "claude"
    path.parent.mkdir()
    path.write_text(FAKE_CLAUDE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "claude-log.jsonl"
    monkeypatch.setenv("STATIC_CLAUDE_CODE_PATH", str(path))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-reach-claude-code")
    monkeypatch.setenv("STATIC_AUTH_TOKEN_SHADOW", "must-not-reach-claude-code")
    return lambda: [json.loads(line) for line in log.read_text().splitlines()]


@posix_only
def test_claude_code_coordinates_with_its_own_tools_off(make_app, fake_claude):
    client, app = make_app(ScriptedProvider())
    use_models(client, cloud(provider="claude_code", model="sonnet"))
    conv, run = new_chat(client, "Plan my week")
    result = wait_run(client, run)
    assert result["status"] == "completed", result
    assert events(result, "plan")
    assert client.get("/api/conversations/" + conv).json()["messages"][-1]["content"] == "All done."
    first, second = fake_claude()
    args = first["args"]
    assert args[:4] == ["-p", "--output-format", "json", "--no-session-persistence"]
    assert args[args.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in args and "--disable-slash-commands" in args
    assert "--model=sonnet" in args
    schema = json.loads(args[args.index("--json-schema") + 1])
    assert (
        "plan_update" in schema["properties"]["tool_calls"]["items"]["properties"]["name"]["enum"]
    )
    assert "You are Static" in first["system"] and "Available tools" in first["system"]
    assert first["cwd_files"] == []
    assert first["api_key"] is None
    assert not [k for k in first["env"] if k.startswith("STATIC_")]
    assert '"role": "tool"' in second["prompt"] and "plan_update" in second["prompt"]
    # Two calls of (10 + 990 cache) input and 100 output tokens at 3 / 15 USD per million.
    assert app.state.store.spending(run) == pytest.approx(2 * (1000 * 3 + 100 * 15) / 1e6)


@posix_only
def test_claude_code_specialist_and_key_variable(make_app, fake_claude, monkeypatch):
    monkeypatch.setenv("MY_CLAUDE_KEY", "sk-ant-for-claude-code")
    provider = ScriptedProvider()
    client, app = make_app(provider)
    local = {"id": "local", "name": "Ollama", "model": "qwen3:4b", "roles": ["coordinator"]}
    use_models(
        client,
        local,
        cloud(provider="claude_code", model="opus", key_env="MY_CLAUDE_KEY", roles=["writer"]),
    )
    provider.tool("agent_delegate", {"role": "writer", "task": "Write a tagline"})
    _, run = new_chat(client)
    result = wait_run(client, run)
    assert result["status"] == "completed", result
    done = next(e for e in events(result, "tool_done") if e["name"] == "agent_delegate")
    assert done["result"]["result"] == "Specialist text"
    (call,) = fake_claude()
    assert "--json-schema" not in call["args"]
    assert call["prompt"].startswith("Write a tagline")
    assert call["api_key"] == "sk-ant-for-claude-code"


@posix_only
def test_claude_code_health_and_sign_in_errors(make_app, fake_claude, monkeypatch):
    client, app = make_app(ScriptedProvider())
    use_models(client, cloud(provider="claude_code", model="sonnet"))
    health = client.post("/api/models/claude/test").json()
    assert health == {"ok": True, "models": ["sonnet"], "message": "Claude Code 9.9.9 is ready"}
    assert client.get("/api/settings").json()["keys"]["claude"] is True
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "logged_out")
    _, run = new_chat(client)
    result = wait_run(client, run)
    assert result["status"] == "failed"
    assert "isn't signed in" in result["error"] and "/login" not in result["error"]


def test_claude_code_missing_or_unsafe_configuration(make_app, monkeypatch, tmp_path):
    monkeypatch.setenv("STATIC_CLAUDE_CODE_PATH", str(tmp_path / "missing-claude"))
    client, app = make_app(ScriptedProvider())
    local = {"id": "local", "name": "Ollama", "model": "qwen3:4b"}
    use_models(client, local, cloud(provider="claude_code", model="sonnet"))
    assert client.get("/api/settings").json()["keys"]["claude"] is False
    assert "not found" in client.post("/api/models/claude/test").json()["message"]
    # An unavailable Claude Code is skipped like a model with a missing key.
    _, run = new_chat(client)
    assert wait_run(client, run)["status"] == "completed"
    model = Model(**cloud(provider="claude_code", model="sonnet"))
    assert model.base_url == ""
    for bad in (
        cloud(provider="claude_code", model="--dangerously-skip-permissions"),
        cloud(provider="claude_code", model="sonnet", local=True),
        cloud(provider="claude_code", model="sonnet", pricing_confirmed=False),
    ):
        with pytest.raises(ValidationError):
            Model(**bad)


# --- MCP servers --------------------------------------------------------------------------


def write_mcp(app, servers):
    Path(app.state.config.root, "mcp.json").write_text(json.dumps({"mcpServers": servers}))


def reload_mcp(client):
    response = client.post("/api/mcp/reload")
    assert response.status_code == 200, response.text
    return {s["name"]: s for s in response.json()["servers"]}


@pytest.fixture
def stdio_server(tmp_path, monkeypatch):
    log = tmp_path / "mcp-log.jsonl"
    monkeypatch.setenv("GREETING_VALUE", "hello from env")
    config = {
        "command": sys.executable,
        "args": [str(ROOT / "mcp_server.py"), str(log)],
        "env": {"GREETING": "${GREETING_VALUE}"},
    }
    return config, lambda: [json.loads(line) for line in log.read_text().splitlines()]


def test_mcp_stdio_tools_become_skills_with_approvals(make_app, stdio_server, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "must-not-reach-mcp")
    config, log = stdio_server
    provider = ScriptedProvider()
    client, app = make_app(provider)
    write_mcp(app, {"demo": config})
    demo = reload_mcp(client)["demo"]
    assert demo["status"] == "connected", demo
    assert demo["tools"] == 4 and demo["info"] == "test-server 1.0" and not demo["remote"]
    skills = {s["name"]: s for s in client.get("/api/skills").json()}
    assert skills["mcp__demo__echo"]["title"] == "Echo"
    assert skills["mcp__demo__echo"]["source"] == "mcp:demo"
    assert not skills["mcp__demo__echo"]["approval"]
    assert skills["mcp__demo__save_note"]["approval"]
    environment = log()[0]
    assert environment["greeting"] == "hello from env"
    assert "BRAVE_API_KEY" not in environment["env"]

    provider.tool("mcp__demo__echo", {"text": "hi there"})
    provider.tool("mcp__demo__fail", {})
    provider.tool("mcp__demo__picture", {})
    conv, run = new_chat(client)
    result = wait_run(client, run)
    assert result["status"] == "completed", result
    echo = next(e for e in events(result, "tool_done") if e["name"] == "mcp__demo__echo")
    assert echo["result"]["content"] == "hi there"
    assert "boom" in events(result, "tool_error")[0]["error"]
    files = client.get("/api/artifacts", params={"conversation_id": conv}).json()
    assert files[0]["name"] == "demo-picture.png"
    request = json.loads(
        next(r for r in provider.requests if r.url.path.endswith("chat/completions")).content
    )
    assert "mcp__<server>__<tool>" in request["messages"][0]["content"]
    echo_schema = next(t for t in request["tools"] if t["function"]["name"] == "mcp__demo__echo")
    assert echo_schema["function"]["parameters"]["properties"]["text"] == {"type": "string"}
    save_schema = next(
        t for t in request["tools"] if t["function"]["name"] == "mcp__demo__save_note"
    )
    assert "$schema" not in save_schema["function"]["parameters"]

    provider.tool("mcp__demo__save_note", {"note": "declined"})
    _, run = new_chat(client)
    waiting = wait_run(client, run)
    assert waiting["status"] == "awaiting_approval"
    approval = waiting["approvals"][0]
    assert approval["args"]["server"] == "demo" and approval["args"]["tool"] == "save.note"
    assert approval["args"]["arguments"] == {"note": "declined"}
    assert client.post("/api/approvals/" + approval["id"], json={"allow": False}).status_code == 200
    assert wait_run(client, run, "completed")["status"] == "completed"

    provider.tool("mcp__demo__save_note", {"note": "approved"})
    _, run = new_chat(client)
    approval = wait_run(client, run)["approvals"][0]["id"]
    assert client.post("/api/approvals/" + approval, json={"allow": True}).status_code == 200
    assert wait_run(client, run, "completed")["status"] == "completed"
    calls = [entry for entry in log() if "call" in entry]
    assert [c["call"] for c in calls] == ["echo", "fail", "picture", "save.note"]
    assert calls[-1]["arguments"] == {"note": "approved"}

    # Disabled MCP tools are withheld from the model like any skill.
    settings = client.get("/api/settings").json()["settings"]
    settings["disabled_skills"] = ["mcp__demo__echo"]
    assert client.put("/api/settings", json=settings).status_code == 200
    _, run = new_chat(client)
    wait_run(client, run)
    request = json.loads(provider.requests[-1].content)
    assert all(t["function"]["name"] != "mcp__demo__echo" for t in request["tools"])


def test_mcp_approval_policies(make_app, stdio_server):
    config, log = stdio_server
    client, app = make_app(ScriptedProvider())
    write_mcp(
        app, {"strict": {**config, "approval": "always"}, "open": {**config, "approval": "never"}}
    )
    reload_mcp(client)
    skills = {s["name"]: s["approval"] for s in client.get("/api/skills").json()}
    assert skills["mcp__strict__echo"] and skills["mcp__strict__save_note"]
    assert not skills["mcp__open__echo"] and not skills["mcp__open__save_note"]


class HttpMcpFake:
    """A Streamable HTTP MCP server answering with JSON or server-sent events."""

    def __init__(self):
        self.requests, self.provider = [], ScriptedProvider()

    def __call__(self, request):
        if request.url.host != "mcp.example.com":
            return self.provider(request)
        self.requests.append(request)
        if request.method == "DELETE":
            return httpx.Response(200)
        message = json.loads(request.content)
        if "id" not in message:
            return httpx.Response(202)
        if message["method"] == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "remote", "version": "2"},
            }
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": message["id"], "result": result},
                headers={"Mcp-Session-Id": "session-1"},
            )
        if message["method"] == "tools/list":
            tool = {
                "name": "lookup",
                "description": "Look up a word.",
                "inputSchema": {"type": "object"},
            }
            result = {"tools": [tool]}
        else:
            result = {"content": [{"type": "text", "text": "A small bread roll."}]}
        stream = (
            'event: message\ndata: {"jsonrpc": "2.0", "method": "notifications/progress"}\n\n'
            f"data: {json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': result})}\n\n"
        )
        return httpx.Response(
            200, content=stream.encode(), headers={"Content-Type": "text/event-stream"}
        )


def test_mcp_http_server_sessions_streams_and_local_mode(make_app, monkeypatch):
    monkeypatch.setenv("REMOTE_MCP_TOKEN", "remote-secret")
    fake = HttpMcpFake()
    client, app = make_app(fake)
    write_mcp(
        app,
        {
            "remote": {
                "type": "http",
                "url": "https://mcp.example.com/mcp",
                "headers": {"Authorization": "Bearer ${REMOTE_MCP_TOKEN}"},
                "approval": "never",
            }
        },
    )
    remote = reload_mcp(client)["remote"]
    assert remote["status"] == "connected", remote
    assert remote["remote"] and remote["target"] == "mcp.example.com"
    assert "remote-secret" not in client.get("/api/mcp").text
    initialize, initialized, listing = fake.requests[:3]
    assert initialize.headers["authorization"] == "Bearer remote-secret"
    assert "text/event-stream" in initialize.headers["accept"]
    assert initialized.headers["mcp-session-id"] == "session-1"
    assert listing.headers["mcp-protocol-version"] == "2025-03-26"

    fake.provider.tool("mcp__remote__lookup", {"word": "bun"})
    _, run = new_chat(client)
    result = wait_run(client, run)
    done = next(e for e in events(result, "tool_done") if e["name"] == "mcp__remote__lookup")
    assert done["result"]["content"] == "A small bread roll."

    fake.provider.tool("mcp__remote__lookup", {"word": "bun"})
    _, run = new_chat(client, mode="local")
    result = wait_run(client, run)
    assert "local-only mode" in events(result, "tool_error")[0]["error"]
    assert len([r for r in fake.requests if b"tools/call" in r.content]) == 1


def test_mcp_configuration_problems_are_reported(make_app, monkeypatch):
    monkeypatch.delenv("UNSET_MCP_VALUE", raising=False)
    client, app = make_app(ScriptedProvider())
    assert client.get("/api/mcp").json()["servers"] == []
    write_mcp(
        app,
        {
            "both": {"command": "x", "url": "https://mcp.example.com"},
            "legacy": {"type": "sse", "url": "https://mcp.example.com/sse"},
            "plain": {"url": "http://mcp.example.com/mcp"},
            "variable": {"command": "${UNSET_MCP_VALUE}"},
            "missing": {"command": "static-test-command-that-does-not-exist"},
            "bad name!": {"command": "x"},
            "off": {"command": "x", "disabled": True},
        },
    )
    servers = reload_mcp(client)
    assert "either a command" in servers["both"]["error"]
    assert "legacy SSE" in servers["legacy"]["error"]
    assert "HTTPS" in servers["plain"]["error"]
    assert "Set UNSET_MCP_VALUE" in servers["variable"]["error"]
    assert "Could not start" in servers["missing"]["error"]
    assert "letters, digits" in servers["bad name!"]["error"]
    assert servers["off"]["status"] == "disabled"
    assert all(s["status"] in ("error", "disabled") for s in servers.values())
    Path(app.state.config.root, "mcp.json").write_text("{not json")
    status = client.post("/api/mcp/reload").json()
    assert "not valid JSON" in status["error"] and status["servers"] == []
    _, run = new_chat(client)
    assert wait_run(client, run)["status"] == "completed"


def test_mcp_reload_waits_for_active_runs(make_app, monkeypatch):
    provider = ScriptedProvider()
    client, app = make_app(provider)
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test")
    settings = client.get("/api/settings").json()["settings"]
    settings["media"]["image"] = {
        "model": "a/b",
        "prompt_field": "prompt",
        "inputs": {},
        "reserve_usd": 0.1,
    }
    assert client.put("/api/settings", json=settings).status_code == 200
    provider.tool("media_generate", {"kind": "image", "prompt": "A tiny orange bun"})
    _, run = new_chat(client)
    assert wait_run(client, run)["status"] == "awaiting_approval"
    assert client.post("/api/mcp/reload").status_code == 409
    client.post("/api/runs/" + run + "/stop")
    deadline = time.monotonic() + 5
    while client.post("/api/mcp/reload").status_code != 200:
        assert time.monotonic() < deadline
