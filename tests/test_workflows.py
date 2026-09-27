import io
import json
import zipfile
from pathlib import Path

from conftest import new_chat, wait_run
from pypdf import PdfReader


def test_chat_persists_and_models_receive_context(workspace):
    client, app, provider = workspace
    conv, run = new_chat(client, "Please help me plan")
    assert wait_run(client, run)["status"] == "completed"
    data = client.get("/api/conversations/" + conv).json()
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    assert client.get("/api/conversations").json()[0]["title"] == "Please help me plan"
    assert app.state.store.spending(run) == 0
    request = next(r for r in provider.requests if r.url.path.endswith("chat/completions"))
    assert json.loads(request.content)["tools"]


def test_tools_create_plan_and_downloadable_document(workspace):
    client, app, provider = workspace
    provider.tool("plan_update", {"steps": [{"title": "Draft document", "status": "active"}]})
    provider.tool(
        "file_create",
        {
            "name": "../../my-plan",
            "format": "docx",
            "content": "# My plan\nA useful paragraph\n- First step",
        },
    )
    conv, run = new_chat(client, "Make a document")
    result = wait_run(client, run)
    assert result["status"] == "completed"
    assert any(e["kind"] == "plan" for e in result["events"])
    files = client.get("/api/artifacts").json()
    assert len(files) == 1 and files[0]["name"] == "my-plan.docx"
    response = client.get(f"/api/artifacts/{files[0]['id']}/download")
    assert "attachment" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as doc:
        assert b"A useful paragraph" in doc.read("word/document.xml")
    assert not list(Path(app.state.config.root).parent.glob("my-plan.docx"))


def test_pdf_and_csv_outputs(workspace):
    client, app, provider = workspace
    provider.tool(
        "file_create", {"name": "plan", "format": "pdf", "content": "# Hello\nA real PDF artifact."}
    )
    provider.tool(
        "file_create",
        {
            "name": "data",
            "format": "csv",
            "content": 'name,value\nitem,=HYPERLINK("https://evil.test")',
        },
    )
    _, run = new_chat(client)
    assert wait_run(client, run)["status"] == "completed"
    files = client.get("/api/artifacts").json()
    pdf = next(f for f in files if f["name"].endswith(".pdf"))
    content = client.get(f"/api/artifacts/{pdf['id']}/download").content
    assert "A real PDF artifact." in PdfReader(io.BytesIO(content)).pages[0].extract_text()
    csv = next(f for f in files if f["name"].endswith(".csv"))
    content = client.get(f"/api/artifacts/{csv['id']}/download").text
    assert "'=HYPERLINK" in content


def test_upload_and_read_scoped_files(workspace):
    client, app, provider = workspace
    conv = client.post("/api/conversations", json={}).json()["id"]
    uploaded = client.post(
        f"/api/conversations/{conv}/upload",
        files={"file": ("note.txt", b"A private note", "text/plain")},
    ).json()
    provider.tool("file_read", {"artifact_id": uploaded["id"]})
    run = client.post(
        f"/api/conversations/{conv}/chat",
        json={"message": "Read the note", "attachments": [uploaded["id"]]},
    ).json()["id"]
    assert wait_run(client, run)["status"] == "completed"
    requests = [
        json.loads(r.content) for r in provider.requests if r.url.path.endswith("chat/completions")
    ]
    assert "A private note" in requests[-1]["messages"][-1]["content"]
    other = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(
        f"/api/conversations/{other}/chat",
        json={"message": "Read it", "attachments": [uploaded["id"]]},
    )
    assert response.status_code == 400


def test_specialist_routing_uses_one_bounded_call(workspace):
    client, app, provider = workspace
    provider.tool("agent_delegate", {"role": "writer", "task": "Write a tagline"})
    provider.replies.extend(
        [
            {"role": "assistant", "content": "Little team. Big ideas."},
            {"role": "assistant", "content": "Here is your tagline."},
        ]
    )
    _, run = new_chat(client)
    assert wait_run(client, run)["status"] == "completed"
    requests = [
        json.loads(r.content) for r in provider.requests if r.url.path.endswith("chat/completions")
    ]
    assert len(requests) == 3
    assert "tools" not in requests[1]
    assert "writer specialist" in requests[1]["messages"][0]["content"]


def test_invalid_tool_is_reported_to_model(workspace):
    client, app, provider = workspace
    provider.tool("run_shell", {"command": "echo not allowed"})
    _, run = new_chat(client)
    result = wait_run(client, run)
    assert result["status"] == "completed"
    assert any(e["kind"] == "tool_error" for e in result["events"])


def test_mesh_creates_real_obj(workspace):
    client, app, provider = workspace
    for shape in ("cube", "sphere", "cylinder"):
        provider.tool("mesh_create", {"shape": shape, "name": shape})
    _, run = new_chat(client)
    assert wait_run(client, run)["status"] == "completed"
    assert len(client.get("/api/artifacts").json()) == 3
    for f in client.get("/api/artifacts").json():
        content = client.get(f"/api/artifacts/{f['id']}/download").text
        assert content.count("\nv ") >= 8 and content.count("\nf ") >= 6


def configure_media(client, monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-secret-do-not-expose")
    settings = client.get("/api/settings").json()["settings"]
    settings["media"]["image"] = {
        "model": "example/image",
        "prompt_field": "prompt",
        "inputs": {},
        "reserve_usd": 0.1,
    }
    assert client.put("/api/settings", json=settings).status_code == 200


def test_media_approval_is_one_use_and_outputs_are_downloaded(workspace, monkeypatch):
    client, app, provider = workspace
    configure_media(client, monkeypatch)
    provider.tool("media_generate", {"kind": "image", "prompt": "A tiny orange bun"})
    conv, run = new_chat(client)
    waiting = wait_run(client, run)
    assert waiting["status"] == "awaiting_approval"
    assert not any("/predictions" in r.url.path for r in provider.requests)
    approval = waiting["approvals"][0]["id"]
    assert client.post("/api/approvals/" + approval, json={"allow": True}).status_code == 200
    assert wait_run(client, run, "completed")["status"] == "completed"
    assert client.post("/api/approvals/" + approval, json={"allow": True}).status_code == 400

    async def fake_download(url, limit):
        return url, b"fake-image-for-contract-test", "image/png"

    monkeypatch.setattr("static_ai.media.fetch_public", fake_download)
    assert client.post("/api/media/refresh").status_code == 200
    assert client.get("/api/media").json()[0]["status"] == "succeeded"
    assert len(client.get("/api/artifacts").json()) == 1
    assert app.state.store.spending(run) == 0.1
    assert "test-secret" not in client.get("/api/settings").text


def test_declined_media_never_calls_provider(workspace, monkeypatch):
    client, app, provider = workspace
    configure_media(client, monkeypatch)
    provider.tool("media_generate", {"kind": "image", "prompt": "A tiny orange bun"})
    _, run = new_chat(client)
    approval = wait_run(client, run)["approvals"][0]["id"]
    client.post("/api/approvals/" + approval, json={"allow": False})
    assert wait_run(client, run, "completed")["status"] == "completed"
    assert not any("/predictions" in r.url.path for r in provider.requests)


def test_duplicate_runs_are_rejected_and_stop_removes_approval(workspace, monkeypatch):
    client, app, provider = workspace
    configure_media(client, monkeypatch)
    provider.tool("media_generate", {"kind": "image", "prompt": "A tiny orange bun"})
    conv, run = new_chat(client)
    assert wait_run(client, run)["status"] == "awaiting_approval"
    assert (
        client.post(f"/api/conversations/{conv}/chat", json={"message": "Another"}).status_code
        == 409
    )
    assert len(client.get("/api/conversations/" + conv).json()["messages"]) == 1
    assert client.post("/api/runs/" + run + "/stop").status_code == 200
    result = client.get("/api/runs/" + run).json()
    assert result["status"] == "cancelled" and not result["approvals"]


def test_local_mode_blocks_media_before_approval(workspace, monkeypatch):
    client, app, provider = workspace
    configure_media(client, monkeypatch)
    provider.tool("media_generate", {"kind": "image", "prompt": "A tiny orange bun"})
    _, run = new_chat(client, mode="local")
    data = wait_run(client, run)
    assert data["status"] == "completed" and not data["approvals"]
    assert not client.get("/api/media").json()


def test_shopping_totals_and_unknown_tax(workspace):
    client, app, provider = workspace
    provider.tool(
        "shopping_compare",
        {
            "offers": [
                {"title": "A", "url": "https://example.com/a", "price": 20, "shipping": 10},
                {
                    "title": "B",
                    "url": "https://example.com/b",
                    "price": 25,
                    "shipping": 0,
                    "tax": 2,
                },
            ]
        },
    )
    _, run = new_chat(client)
    data = wait_run(client, run)
    offers = next(e["data"]["offers"] for e in data["events"] if e["kind"] == "shopping")
    assert offers[0]["title"] == "B" and offers[0]["total"] == 27
    assert not offers[1]["tax_included"]


def test_step_limit_stops_recursive_work(workspace):
    client, app, provider = workspace
    app.state.config.settings.max_steps = 1
    provider.tool("file_list", {})
    _, run = new_chat(client)
    result = wait_run(client, run)
    assert result["status"] == "failed" and "Step limit" in result["error"]
