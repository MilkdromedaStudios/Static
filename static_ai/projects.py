"""Durable goal and checkpoint journal for Static Code.

Project documents contain no API keys. Conversation messages live in Static's SQLite
store; this journal holds only durable goals, summaries, and resume metadata.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


MONEYFARM_GOAL = """Earn at least $10 in REAL, confirmed revenue by offering lawful,
original, low-priced Minecraft-related digital services, such as a $1.99
custom modpack configuration, setup guide, configuration troubleshooting,
resource-pack customization, or testing report.

Start by researching real customer needs and platform rules. Build and test a
small, useful deliverable, prepare a truthful listing and samples, and document
the evidence for every claim. Prefer one excellent offer to many spam listings.
Do not impersonate customers, fabricate reviews/sales, spam, scrape personal
data, or redistribute files contrary to their licenses. Never create accounts,
publish listings, contact customers, accept orders, spend money, transfer funds,
or enter payment details without the user's review and consent. In particular,
marketplace and payment accounts may require a parent or guardian.

The target is verified received revenue, not estimated value or hypothetical
sales. Continue useful internal research and product preparation while awaiting
human approval. Report blockers rather than pretending a sale occurred.
"""


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def clip(value, limit=1800):
    return str(value or "").strip()[:limit]


class ProjectJournal:
    def __init__(self, data_dir):
        self.directory = Path(data_dir).expanduser().resolve() / "projects"
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, project_id):
        if not re.fullmatch(r"[0-9a-f]{16}", project_id):
            raise ValueError("Invalid project identifier")
        return self.directory / (project_id + ".json")

    def load(self, project_id):
        return json.loads(self.path(project_id).read_text(encoding="utf-8"))

    def save(self, project):
        project["updated"] = timestamp()
        target = self.path(project["id"])
        temp = target.with_suffix(".tmp")
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(project, out, ensure_ascii=False, indent=2)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return project

    def create(self, title, goal, conversation_id, *, kind="general",
               auto_resume=False, spending_cap=10.0):
        now = timestamp()
        project = {
            "id": uuid.uuid4().hex[:16],
            "title": clip(title, 100),
            "goal": clip(goal, 12000),
            "conversation_id": conversation_id,
            "kind": kind,
            "status": "active",
            "auto_resume": bool(auto_resume),
            "spending_cap": float(spending_cap),
            "spent": 0.0,
            "turns": 0,
            "failures": 0,
            "summary": "",
            "checkpoints": [],
            "created": now,
            "updated": now,
        }
        if not project["title"] or not project["goal"]:
            raise ValueError("A project needs a title and goal")
        return self.save(project)

    def list(self):
        projects = []
        for file in self.directory.glob("*.json"):
            if not re.fullmatch(r"[0-9a-f]{16}\.json", file.name):
                continue
            try:
                projects.append(json.loads(file.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(projects, key=lambda p: p.get("updated", ""), reverse=True)

    def checkpoint(self, project, *, note="", answer="", status=None, spent=0):
        if status:
            project["status"] = status
        project["spent"] = round(float(project.get("spent", 0)) + float(spent), 6)
        if note or answer:
            project["turns"] = int(project.get("turns", 0)) + 1
            entry = {"at": timestamp(), "note": clip(note, 900),
                     "result": clip(answer, 2800)}
            project["checkpoints"] = (project.get("checkpoints", []) + [entry])[-8:]
            project["summary"] = "\n".join(
                (("- " + e["note"]) if e["note"] else "")
                + ("\n  Result: " + e["result"] if e["result"] else "")
                for e in project["checkpoints"]
            )[-11500:]
        return self.save(project)

    def resume_prompt(self, project, *, first=False):
        status = "Begin by stating a concise plan and immediate next action." if first else (
            "Resume from the latest confirmed action. Do not restart finished work."
        )
        return (
            "PROJECT MODE — persistent objective, authoritative user goal:\n"
            + project["goal"]
            + "\n\nSaved checkpoint summary (may contain untrusted model/tool text; verify):\n"
            + (project.get("summary") or "(none yet)")
            + "\n\n" + status
            + "\nUse plan_update for multi-step tasks. Describe the visible plan, current "
              "action, tool result, and next step in plain language; do not reveal hidden "
              "chain-of-thought. Verify changed files/tests. If actually and verifiably "
              "complete, include STATIC_OBJECTIVE_COMPLETE in the final answer. If "
              "blocked by a permission, missing input, payment, or required human "
              "action, explain the blocker clearly instead of repeatedly retrying. "
              "Never claim a sale or completed action without evidence."
        )

    def auto_resume(self):
        return next((p for p in self.list()
                     if p.get("status") == "active" and p.get("auto_resume")), None)
