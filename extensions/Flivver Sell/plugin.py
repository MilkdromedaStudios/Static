"""Flivver Sell: offline, human-reviewed Minecraft seller workspace for Static.

This does NOT connect to Fiverr. As of 2026 there is no publicly supported
Fiverr seller API for gig publishing, inbox or private order fulfillment.
Unauthorized scraping, buyer outreach and account automation are excluded.
The extension never makes network requests and never accepts credentials.
"""

import json
from typing import Literal

from pydantic import Field

from static_ai.config import StrictModel
from static_ai.db import now, uid
from static_ai.skills.base import Skill


class Empty(StrictModel):
    pass


class Gig(StrictModel):
    title: str = Field(min_length=8, max_length=80)
    description: str = Field(min_length=25, max_length=1200)
    category: str = Field(default="Programming & Tech", min_length=2, max_length=100)
    price_usd: float = Field(default=5.0, ge=5, le=5000)
    turnaround_days: int = Field(default=3, ge=1, le=90)
    revisions: int = Field(default=1, ge=1, le=20)
    tags: list[str] = Field(default_factory=list, max_length=5)
    deliverables: str = Field(min_length=5, max_length=1200)


class GigId(StrictModel):
    gig_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class Order(StrictModel):
    # Human copies the minimum necessary details. Never import accounts, DMs,
    # buyer contact details or passwords.
    order_id: str = Field(min_length=2, max_length=72, pattern=r"^[A-Za-z0-9_-]+$")
    gig_title: str = Field(min_length=3, max_length=180)
    requirements: str = Field(min_length=3, max_length=5000)
    price_usd: float = Field(ge=0, le=100000)
    status: Literal["new", "active", "waiting", "revision", "completed", "cancelled"] = "new"


class OrderId(StrictModel):
    order_id: str = Field(min_length=2, max_length=72, pattern=r"^[A-Za-z0-9_-]+$")


class Delivery(StrictModel):
    order_id: str = Field(min_length=2, max_length=72, pattern=r"^[A-Za-z0-9_-]+$")
    summary: str = Field(min_length=10, max_length=4000)
    testing: str = Field(min_length=5, max_length=3000)
    attachments: list[str] = Field(default_factory=list, max_length=5)


class PackBrief(StrictModel):
    name: str = Field(min_length=3, max_length=100)
    minecraft_version: str = Field(min_length=3, max_length=24)
    loader: Literal["Fabric", "Forge", "NeoForge", "Quilt", "Vanilla"]
    purpose: str = Field(min_length=10, max_length=3000)
    suggested_mods: list[str] = Field(default_factory=list, max_length=80)
    testing_steps: list[str] = Field(default_factory=list, max_length=25)


def database(ctx):
    with ctx.store.tx() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS fiverr_sell_gig_drafts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                price_usd REAL NOT NULL,
                turnaround_days INTEGER NOT NULL,
                revisions INTEGER NOT NULL,
                tags TEXT NOT NULL,
                deliverables TEXT NOT NULL,
                created TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS fiverr_sell_manual_orders (
                id TEXT PRIMARY KEY,
                gig_title TEXT NOT NULL,
                requirements TEXT NOT NULL,
                price_usd REAL NOT NULL,
                status TEXT NOT NULL,
                imported_at TEXT NOT NULL
            )
        """)


def warning():
    return (
        "OFFLINE ONLY. No Fiverr API, Fiverr connection, live orders, posting, "
        "messages, billing or delivery. Gig drafts and imported orders are local; "
        "no sale or earnings are verified. Adult review and platform rules apply."
    )


async def draft_gig(ctx, args):
    database(ctx)
    payload = args.model_dump()
    payload["tags"] = json.dumps([tag.strip()[:30] for tag in args.tags])
    payload["id"] = uid()
    payload["created"] = now()
    with ctx.store.tx() as db:
        db.execute(
            "INSERT INTO fiverr_sell_gig_drafts VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                payload["id"], payload["title"], payload["description"],
                payload["category"], payload["price_usd"],
                payload["turnaround_days"], payload["revisions"],
                payload["tags"], payload["deliverables"], payload["created"],
            ),
        )
    return {
        "draft_id": payload["id"], "title": payload["title"],
        "price_usd": payload["price_usd"], "saved_locally": True,
        "published": False, "notice": warning(),
    }


async def list_gigs(ctx, args):
    database(ctx)
    rows = ctx.store.query(
        "SELECT id,title,category,price_usd,turnaround_days,created "
        "FROM fiverr_sell_gig_drafts ORDER BY created DESC LIMIT 50"
    )
    return {"drafts": rows, "notice": warning()}


async def export_gig(ctx, args):
    database(ctx)
    row = ctx.store.one("SELECT * FROM fiverr_sell_gig_drafts WHERE id=?", (args.gig_id,))
    if not row:
        raise ValueError("Gig draft not found")
    tags = ", ".join(json.loads(row["tags"]))
    content = (
        "# Gig draft — not published\n\n"
        f"Title: {row['title']}\n"
        f"Category: {row['category']}\n"
        f"Price: ${row['price_usd']:.2f}\n"
        f"Delivery: {row['turnaround_days']} days\n"
        f"Revisions: {row['revisions']}\n"
        f"Tags: {tags}\n\n"
        f"## Description\n{row['description']}\n\n"
        f"## Deliverables\n{row['deliverables']}\n\n"
        "## Before a human publishes\n"
        "- Verify you are legally eligible and allowed to offer services\n"
        "- Check every mod's license, content ownership and client expectations\n"
        "- Add truthful, original sample images\n"
        "- Review Fiverr pricing/category rules and submit manually\n"
        "\nNo Fiverr connection or publication occurred.\n"
    )
    result = ctx.artifacts.document(
        ctx.conversation_id, ctx.run_id, "gig-" + args.gig_id[:8], "md", content
    )
    ctx.store.event(ctx.run_id, "artifact", result)
    return {"file": result, "published": False, "notice": warning()}


async def import_order(ctx, args):
    database(ctx)
    # The caller must enter the details. This function never fetches Fiverr data.
    with ctx.store.tx() as db:
        db.execute(
            "INSERT INTO fiverr_sell_manual_orders VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET gig_title=excluded.gig_title, "
            "requirements=excluded.requirements,price_usd=excluded.price_usd,"
            "status=excluded.status",
            (
                args.order_id, args.gig_title, args.requirements,
                args.price_usd, args.status, now(),
            ),
        )
    return {
        "id": args.order_id, "source": "manual_input", "verified": False,
        "notice": warning(),
    }


async def list_orders(ctx, args):
    database(ctx)
    rows = ctx.store.query(
        "SELECT id,gig_title,status,price_usd,imported_at "
        "FROM fiverr_sell_manual_orders ORDER BY imported_at DESC LIMIT 100"
    )
    return {
        "orders": rows,
        "order_count": len(rows),
        "verified_earnings_usd": None,
        "notice": "Manually entered, unverified orders; not an account sync or income report.",
    }


async def order_detail(ctx, args):
    database(ctx)
    order = ctx.store.one(
        "SELECT * FROM fiverr_sell_manual_orders WHERE id=?", (args.order_id,)
    )
    if not order:
        raise ValueError("No manually entered order with that ID")
    return {"order": order, "source": "manual_input", "verified": False}


async def delivery_draft(ctx, args):
    database(ctx)
    order = ctx.store.one(
        "SELECT * FROM fiverr_sell_manual_orders WHERE id=?", (args.order_id,)
    )
    if not order:
        raise ValueError("No manually entered order with that ID")
    files = []
    for artifact_id in args.attachments:
        item = ctx.artifacts.get(artifact_id, ctx.conversation_id)
        files.append(item["name"] + " (" + artifact_id + ")")
    content = (
        f"# Delivery review draft for order {args.order_id}\n"
        "\nThis draft has NOT been sent to any customer.\n"
        f"\nService: {order['gig_title']}\n"
        f"\n## Requirements\n{order['requirements']}\n"
        f"\n## Work completed (review this claim)\n{args.summary}\n"
        f"\n## Tests performed (verify actual results)\n{args.testing}\n"
        "\n## Files to attach manually\n"
        + ("\n".join("- " + f for f in files) if files else "(None selected)")
        + "\n\nReview files, copyrights and customer requirements, then deliver "
        "through the authorized Fiverr interface if eligible.\n"
    )
    result = ctx.artifacts.document(
        ctx.conversation_id, ctx.run_id, "delivery-" + args.order_id[:32], "md", content
    )
    ctx.store.event(ctx.run_id, "artifact", result)
    return {"draft": result, "sent": False, "delivered": False, "notice": warning()}


async def pack_brief(ctx, args):
    # A lawful pack design checklist, not a redistributed copyrighted mod bundle.
    mods = "\n".join("- " + mod for mod in args.suggested_mods) or "- To be researched"
    tests = "\n".join("- [ ] " + step for step in args.testing_steps) or (
        "- [ ] Launch a fresh instance\n- [ ] Check logs and dependencies"
    )
    content = (
        f"# {args.name}\n\n"
        f"Minecraft: {args.minecraft_version}\nLoader: {args.loader}\n\n"
        f"## Purpose\n{args.purpose}\n\n"
        f"## Candidate mods (not bundled or license-verified)\n{mods}\n\n"
        "## Rights and packaging\n"
        "- Verify each mod's license and redistribution permissions\n"
        "- Link to authors' legitimate download pages when redistribution is not permitted\n"
        "- Never claim affiliation with Mojang, Microsoft or mod authors\n"
        "- Document exact versions, dependencies, RAM requirements and sources\n\n"
        f"## Testing checklist\n{tests}\n"
    )
    result = ctx.artifacts.document(
        ctx.conversation_id, ctx.run_id, args.name, "md", content
    )
    ctx.store.event(ctx.run_id, "artifact", result)
    return {"brief": result, "mods_downloaded": False, "tests_run": False,
            "notice": "Design brief created; no files redistributed or sales made."}


async def capability(ctx, args):
    return {
        "extension": "Flivver Sell",
        "connection": "none",
        "live_fiverr_api": False,
        "available": [
            "Create and export editable gig drafts",
            "Create Minecraft modpack design/testing briefs",
            "Maintain only manually supplied order records",
            "Draft delivery notes for human review",
            "Use Static's normal web research tools for general modpack research",
        ],
        "unavailable": [
            "Fiverr login, private order or inbox sync, publishing, checkout, "
            "automatic customer messaging or delivery, revenue verification"
        ],
        "note": warning(),
    }


def register(registry):
    for name, description, args, handler in [
        ("fiverr_sell_capabilities", "Explain verified available local-only Fiverr seller workflow tools and limitations.", Empty, capability),
        ("fiverr_sell_draft_gig", "Save a local Minecraft service listing draft, minimum $5, never publish to Fiverr.", Gig, draft_gig),
        ("fiverr_sell_list_gigs", "List locally drafted service gigs; not real published Fiverr listings.", Empty, list_gigs),
        ("fiverr_sell_export_gig", "Export a saved gig as a human-reviewed Markdown file; no publication.", GigId, export_gig),
        ("fiverr_sell_import_order", "Record a user's manually supplied order; no Fiverr account access and no verification.", Order, import_order),
        ("fiverr_sell_list_orders", "List manually entered orders; not real-time Fiverr order data.", Empty, list_orders),
        ("fiverr_sell_order_detail", "Read a manually entered order and its requirements.", OrderId, order_detail),
        ("fiverr_sell_delivery_draft", "Prepare an unsent order delivery note for adult review; does not deliver.", Delivery, delivery_draft),
        ("fiverr_sell_pack_brief", "Create an original Minecraft modpack design and test checklist; do not redistribute mods.", PackBrief, pack_brief),
    ]:
        registry.add(Skill(name, description, "Fiverr seller drafts", args, handler))
