"""Extension manager and offline Fiverr seller workflow regressions."""

from conftest import new_chat, wait_run

from static_ai.extensions import ExtensionManager


def test_extension_requires_explicit_opt_in(workspace):
    client, app, _ = workspace
    discovered = client.get("/api/extensions").json()
    extension = next(e for e in discovered if e["id"] == "fiverr-sell")
    assert not extension["active"]
    assert extension["name"] == "Flivver Sell"
    names = {skill["name"] for skill in client.get("/api/skills").json()}
    assert "fiverr_sell_draft_gig" not in names

    enabled = client.post("/api/extensions/fiverr-sell/enable")
    assert enabled.status_code == 200
    assert "fiverr_sell_draft_gig" in enabled.json()["tools"]
    names = {skill["name"] for skill in client.get("/api/skills").json()}
    assert "fiverr_sell_draft_gig" in names

    disabled = client.post("/api/extensions/fiverr-sell/disable")
    assert disabled.status_code == 200
    names = {skill["name"] for skill in client.get("/api/skills").json()}
    assert "fiverr_sell_draft_gig" not in names


def test_enabled_extension_persists_across_manager_restarts(tmp_path):
    manager = ExtensionManager(tmp_path)
    assert not any(s.name.startswith("fiverr_sell") for s in manager.skills())
    assert manager.enable("Flivver Sell")["enabled"]
    reloaded = ExtensionManager(tmp_path)
    assert any(s.name == "fiverr_sell_draft_gig" for s in reloaded.skills())
    reloaded.disable("fiverr-sell")
    assert not ExtensionManager(tmp_path).skills()


def test_gig_draft_and_export_never_publish(workspace):
    client, app, provider = workspace
    client.post("/api/extensions/fiverr-sell/enable")
    provider.tool(
        "fiverr_sell_draft_gig",
        {
            "title": "I will assemble a tested Minecraft Fabric modpack",
            "description": "A custom lightweight setup with clear installation steps, "
            "dependency checks and an honest list of any untested mods.",
            "category": "Programming & Tech",
            "price_usd": 5,
            "turnaround_days": 3,
            "revisions": 1,
            "tags": ["minecraft", "modpack"],
            "deliverables": "A documented pack design and installation instructions.",
        },
    )
    conversation, run = new_chat(client, "Prepare an unpublished gig draft")
    response = wait_run(client, run)
    assert response["status"] == "completed"
    event = next(
        e for e in response["events"]
        if e["kind"] == "tool_done" and e["data"]["name"] == "fiverr_sell_draft_gig"
    )
    assert event["data"]["result"]["published"] is False
    draft_id = event["data"]["result"]["draft_id"]
    provider.tool("fiverr_sell_export_gig", {"gig_id": draft_id})
    continued = client.post(
        f"/api/conversations/{conversation}/chat", json={"message": "Export the draft"}
    ).json()["id"]
    response = wait_run(client, continued)
    assert response["status"] == "completed"
    markdown = client.get("/api/artifacts").json()
    assert any(x["name"].startswith("gig-") for x in markdown)


def test_order_import_is_not_verified_revenue(workspace):
    client, app, provider = workspace
    client.post("/api/extensions/fiverr-sell/enable")
    provider.tool(
        "fiverr_sell_import_order",
        {
            "order_id": "manual-123",
            "gig_title": "Minecraft dependency troubleshooting",
            "requirements": "Review the crash log and write troubleshooting steps.",
            "price_usd": 10,
            "status": "active",
        },
    )
    conversation, run = new_chat(client, "Enter the manually supplied order")
    result = wait_run(client, run)
    assert result["status"] == "completed"
    assert any(e["kind"] == "tool_done" for e in result["events"])

    provider.tool("fiverr_sell_list_orders", {})
    continued = client.post(
        f"/api/conversations/{conversation}/chat", json={"message": "List imported orders"}
    ).json()["id"]
    response = wait_run(client, continued)
    orders = next(
        e["data"]["result"] for e in response["events"]
        if e["kind"] == "tool_done" and e["data"]["name"] == "fiverr_sell_list_orders"
    )
    assert orders["verified_earnings_usd"] is None
    assert orders["orders"][0]["id"] == "manual-123"


def test_gig_price_below_fiverr_minimum_is_rejected(workspace):
    client, app, provider = workspace
    client.post("/api/extensions/fiverr-sell/enable")
    provider.tool(
        "fiverr_sell_draft_gig",
        {
            "title": "A small Minecraft modpack",
            "description": "A service to create a lightweight Minecraft modpack",
            "deliverables": "Modpack setup instructions",
            "price_usd": 1.99,
        },
    )
    _, run = new_chat(client, "Make a below-minimum gig")
    result = wait_run(client, run)
    assert any(e["kind"] == "tool_error" for e in result["events"])
