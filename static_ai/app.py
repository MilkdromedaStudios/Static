import asyncio
import hmac
import json
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .artifacts import Artifacts
from .config import Config, Settings, StrictModel, env
from .db import Store, now, uid
from .engine import Engine
from .media import MediaService
from .providers import Providers
from .skills import create_registry
from .skills.planning import Step


class Chat(StrictModel):
    message: str = Field(min_length=1, max_length=16000)
    mode: str = Field(default="economy", pattern=r"^(economy|local)$")
    budget_usd: float | None = Field(default=None, ge=0, le=100)
    attachments: list[str] = Field(default_factory=list, max_length=5)


class Decision(StrictModel):
    allow: bool


class Title(StrictModel):
    title: str = Field(default="New conversation", min_length=1, max_length=100)


class TaskCreate(StrictModel):
    title: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1, max_length=12000)
    category: Literal["work", "life", "research", "creative"] = "life"


class TaskEdit(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    objective: str | None = Field(default=None, min_length=1, max_length=12000)
    status: Literal["open", "done"] | None = None
    steps: list[Step] | None = Field(default=None, max_length=12)


class TaskStart(StrictModel):
    mode: Literal["economy", "local"] = "economy"
    budget_usd: float | None = Field(default=None, ge=0, le=100)


def create_app(data_dir=None, transport=None):
    config = Config(Path(data_dir or env("DATA_DIR", "data")))
    # Back up through SQLite so an existing WAL is included. Keep the original for rollback.
    legacy = config.root / "buns.db"
    target = config.root / "static.db"
    if legacy.exists() and not target.exists():
        temporary = config.root / "static-migration.tmp"
        with closing(sqlite3.connect(legacy)) as old, closing(sqlite3.connect(temporary)) as new:
            old.backup(new)
        temporary.replace(target)
    store = Store(config.root / "static.db")
    artifacts = Artifacts(config.root, store)
    providers = Providers(config, store, transport)
    media = MediaService(config, store, artifacts, transport)
    registry = create_registry()
    engine = Engine(config, store, providers, artifacts, media, registry)
    token = env("AUTH_TOKEN")
    allowed_hosts = env("ALLOWED_HOSTS", "localhost,127.0.0.1,::1").split(",")

    @asynccontextmanager
    async def lifespan(app):
        store.execute(
            "UPDATE runs SET status='interrupted',error='Server restarted. Completed artifacts are saved; send a follow-up to continue.' WHERE status IN ('running','queued')"
        )
        store.execute(
            "UPDATE media_jobs SET status='unknown',error='Submission interrupted. Check the provider dashboard before retrying.' WHERE status='submitting'"
        )
        poller = asyncio.create_task(media.loop())
        yield
        poller.cancel()
        tasks = list(engine.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(poller, *tasks, return_exceptions=True)

    app = FastAPI(
        title="Static",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.engine, app.state.store, app.state.config = engine, store, config
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def access(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            if token and not hmac.compare_digest(
                request.headers.get("authorization", ""), "Bearer " + token
            ):
                return JSONResponse(
                    {"detail": "Unlock this workspace with its access token."}, status_code=401
                )
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin = request.headers.get("origin")
                if origin and (
                    urlsplit(origin).netloc != request.headers.get("host")
                    or urlsplit(origin).scheme not in ("http", "https")
                ):
                    return JSONResponse(
                        {"detail": "Cross-origin writes are blocked"}, status_code=403
                    )
                # Custom header prevents cross-site form posts to a local unauthenticated app.
                if request.headers.get("x-static-client") != "web":
                    return JSONResponse({"detail": "Missing client header"}, status_code=403)
                try:
                    if int(request.headers.get("content-length", "0")) > 5_500_000:
                        return JSONResponse({"detail": "Request too large"}, status_code=413)
                except ValueError:
                    return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith("/api/") else "no-cache"
        )
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def conversation(conversation_id):
        if not store.one("SELECT id FROM conversations WHERE id=?", (conversation_id,)):
            raise HTTPException(404, "Conversation not found")

    @app.get("/api/health")
    async def health():
        return {"ok": True, "version": __version__, "auth_enabled": bool(token)}

    @app.get("/api/settings")
    async def settings():
        return {**config.public(), "spent_today": store.spending(), "date_basis": "UTC"}

    @app.put("/api/settings")
    async def save_settings(settings: Settings):
        if store.one(
            "SELECT id FROM runs WHERE status IN ('queued','running','awaiting_approval')"
        ):
            raise HTTPException(409, "Finish or stop active tasks before changing settings")
        config.save(settings)
        return config.public()

    @app.post("/api/models/{model_id}/test")
    async def test_model(model_id: str):
        model = next((m for m in config.settings.models if m.id == model_id), None)
        if not model:
            raise HTTPException(404, "Model not found")
        return await providers.health(model)

    @app.get("/api/skills")
    async def skills():
        return [
            {
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "approval": s.approval,
                "enabled": s.name not in config.settings.disabled_skills,
            }
            for s in registry.skills.values()
        ]

    @app.get("/api/conversations")
    async def conversations():
        return store.query("SELECT * FROM conversations ORDER BY created DESC")

    def task_record(task_id):
        item = store.one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not item:
            raise HTTPException(404, "Task not found")
        item["steps"] = json.loads(item["steps"])
        item["run"] = store.one(
            "SELECT id,status,error FROM runs WHERE conversation_id=? ORDER BY created DESC LIMIT 1",
            (item["conversation_id"],),
        )
        return item

    @app.get("/api/tasks")
    async def list_tasks():
        return [
            task_record(t["id"]) for t in store.query("SELECT id FROM tasks ORDER BY updated DESC")
        ]

    @app.post("/api/tasks", status_code=201)
    async def create_task(body: TaskCreate):
        if not body.title.strip() or not body.objective.strip():
            raise ValueError("Give the task a title and an objective")
        task_id, conv_id, created = uid(), uid(), now()
        with store.tx() as db:
            db.execute(
                "INSERT INTO conversations VALUES(?,?,?)", (conv_id, body.title.strip(), created)
            )
            db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    body.title.strip(),
                    body.objective.strip(),
                    body.category,
                    "open",
                    "[]",
                    conv_id,
                    created,
                    created,
                ),
            )
        return task_record(task_id)

    @app.patch("/api/tasks/{task_id}")
    async def edit_task(task_id: str, body: TaskEdit):
        task_record(task_id)
        updates = body.model_dump(exclude_none=True)
        if any(isinstance(v, str) and not v.strip() for v in updates.values()):
            raise ValueError("Task fields cannot be blank")
        if "steps" in updates:
            updates["steps"] = json.dumps(updates["steps"])
        if updates:
            updates["updated"] = now()
            store.execute(
                "UPDATE tasks SET " + ",".join(k + "=?" for k in updates) + " WHERE id=?",
                (*updates.values(), task_id),
            )
        return task_record(task_id)

    @app.post("/api/tasks/{task_id}/start", status_code=202)
    async def start_task(task_id: str, body: TaskStart):
        item = task_record(task_id)
        if item["status"] == "done":
            raise HTTPException(409, "Reopen this task before continuing")
        result = await chat(
            item["conversation_id"],
            Chat(
                message=f"Help me make progress on this saved task: {item['title']}\n\n{item['objective']}\n\nSaved checklist: {json.dumps(item['steps'])}\n\nUse a plan for complex work. Use existing conversation results and completed steps before doing more work.",
                **body.model_dump(),
            ),
        )
        return {**result, "conversation_id": item["conversation_id"]}

    @app.post("/api/conversations", status_code=201)
    async def new_conversation(body: Title):
        item = {"id": uid(), "title": body.title, "created": now()}
        store.execute("INSERT INTO conversations VALUES(?,?,?)", tuple(item.values()))
        return item

    @app.get("/api/conversations/{conversation_id}")
    async def get_conversation(conversation_id: str):
        conversation(conversation_id)
        return {
            "messages": store.query(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created",
                (conversation_id,),
            ),
            "runs": store.query(
                "SELECT id,status,mode,budget,error,created FROM runs WHERE conversation_id=? ORDER BY created DESC",
                (conversation_id,),
            ),
        }

    @app.post("/api/conversations/{conversation_id}/chat", status_code=202)
    async def chat(conversation_id: str, body: Chat):
        conversation(conversation_id)
        if not body.message.strip():
            raise ValueError("Write a message first")
        if len(engine.tasks) >= 8:
            raise HTTPException(429, "Too many tasks. Wait for a running task to finish.")
        attachment_text = ""
        for artifact_id in body.attachments:
            item = artifacts.get(artifact_id, conversation_id)
            attachment_text += f"\nAttachment: {item['name']} (artifact_id: {artifact_id})"
        run_id = uid()
        try:
            with store.tx() as db:
                count = db.execute(
                    "SELECT COUNT(*) FROM messages WHERE conversation_id=?", (conversation_id,)
                ).fetchone()[0]
                if (
                    not count
                    and not db.execute(
                        "SELECT id FROM tasks WHERE conversation_id=?", (conversation_id,)
                    ).fetchone()
                ):
                    db.execute(
                        "UPDATE conversations SET title=? WHERE id=?",
                        (body.message[:60], conversation_id),
                    )
                db.execute(
                    "INSERT INTO messages VALUES(?,?,?,?,?)",
                    (uid(), conversation_id, "user", body.message.strip() + attachment_text, now()),
                )
                db.execute(
                    "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        conversation_id,
                        "queued",
                        body.mode,
                        body.budget_usd
                        if body.budget_usd is not None
                        else config.settings.run_budget_usd,
                        "{}",
                        "",
                        now(),
                        now(),
                    ),
                )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "This conversation already has an active task") from None
        engine.start(run_id)
        return {"id": run_id, "status": "queued"}

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str, after: int = 0):
        run = store.one(
            "SELECT id,conversation_id,status,mode,budget,error FROM runs WHERE id=?", (run_id,)
        )
        if not run:
            raise HTTPException(404, "Run not found")
        events = store.query(
            "SELECT * FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT 100",
            (run_id, max(0, after)),
        )
        for event in events:
            event["data"] = json.loads(event["data"])
        approvals = store.query(
            "SELECT * FROM approvals WHERE run_id=? AND status='pending'", (run_id,)
        )
        for approval in approvals:
            approval["args"] = json.loads(approval["args"])
        return {**run, "spent": store.spending(run_id), "events": events, "approvals": approvals}

    @app.post("/api/runs/{run_id}/stop")
    async def stop(run_id: str):
        run = store.one("SELECT status FROM runs WHERE id=?", (run_id,))
        if not run:
            raise HTTPException(404, "Run not found")
        if run["status"] in ("queued", "running", "awaiting_approval"):
            await engine.stop(run_id)
        return {"ok": True}

    @app.post("/api/approvals/{approval_id}")
    async def decide(approval_id: str, decision: Decision):
        engine.approval(approval_id, decision.allow)
        return {"ok": True}

    @app.get("/api/artifacts")
    async def list_artifacts(conversation_id: str | None = None):
        return store.query(
            "SELECT id,name,size,mime,conversation_id,created FROM artifacts"
            + (" WHERE conversation_id=?" if conversation_id else "")
            + " ORDER BY created DESC",
            (conversation_id,) if conversation_id else (),
        )

    @app.get("/api/artifacts/{artifact_id}/download")
    async def download(artifact_id: str):
        item = artifacts.get(artifact_id)
        return FileResponse(
            item["path"], filename=item["name"], media_type="application/octet-stream"
        )

    @app.post("/api/conversations/{conversation_id}/upload")
    async def upload(conversation_id: str, file: UploadFile = File(...)):
        conversation(conversation_id)
        if Path(file.filename or "").suffix.lower() not in (
            ".txt",
            ".md",
            ".json",
            ".csv",
            ".pdf",
            ".py",
            ".html",
            ".obj",
            ".yaml",
            ".yml",
            ".js",
            ".css",
            ".ics",
            ".eml",
        ):
            raise ValueError("Upload a text, code, CSV, JSON or PDF file (up to 5 MB)")
        content = await file.read(5_000_001)
        if len(content) > 5_000_000:
            raise HTTPException(413, "File exceeds 5 MB")
        return artifacts.save(
            conversation_id,
            "",
            file.filename or "upload.txt",
            content,
            file.content_type or "application/octet-stream",
        )

    @app.get("/api/media")
    async def jobs():
        return store.query("SELECT * FROM media_jobs ORDER BY created DESC LIMIT 100")

    @app.post("/api/media/refresh")
    async def refresh_media():
        await media.refresh()
        return {"ok": True}

    @app.post("/api/media/{job_id}/cancel")
    async def cancel_media(job_id: str):
        await media.cancel(job_id)
        return {"ok": True}

    static = Path(__file__).parent / "static"
    app.mount("/assets", StaticFiles(directory=static), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(static / "index.html")

    @app.get("/{page}.html")
    async def page(page: str):
        if page == "mini":
            return FileResponse(static / "mini.html")
        if page not in (
            "index",
            "chat",
            "tasks",
            "create",
            "library",
            "skills",
            "connections",
            "settings",
        ):
            raise HTTPException(404, "Page not found")
        return FileResponse(static / "index.html")

    return app
