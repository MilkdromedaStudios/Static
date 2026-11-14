"""Static Code: persistent, keyboard-first terminal interface.

The same application service powers the web UI and terminal; messages and runs
are saved in Static's SQLite workspace.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from .app import create_app
from .projects import MONEYFARM_GOAL, ProjectJournal
from .terminal_setup import configure, load_credentials
from .terminal_ui import choose_chat, show_banner, show_bubble, show_event

COMMANDS = (
    "/help",
    "/exit",
    "/quit",
    "/new",
    "/resume",
    "/sessions",
    "/history",
    "/tasks",
    "/skills",
    "/files",
    "/mode",
    "/status",
    "/clear",
    "/setup",
    "/models",
    "/mcp",
    "/media",
    "/task-new",
    "/task-start",
    "/upload",
    "/settings",
    "/rename",
    "/download",
    "/task-done",
    "/task-reopen",
    "/media-refresh",
    "/media-cancel",
    "/mcp-reload",
    "/budget",
    "/auto",
    "/continuous",
    "/both",
    "/save",
    "/project",
    "/projects",
    "/goal",
    "/pause",
    "/moneyfarm",
    "/extension",
)


class Terminal:
    def __init__(self, client, data_dir, mode, conversation_id=None):
        self.client = client
        self.data_dir = Path(data_dir).resolve()
        self.mode = mode
        self.conversation_id = conversation_id
        self.session = None
        self.active_run = None
        self.config = None
        self.budget = None
        self.pending_attachments = []
        self.auto_approve = False
        self.continuous = False
        self.continuous_limit = 10.0
        self.continuous_spent = 0.0
        self.journal = ProjectJournal(self.data_dir)
        self.project = None
        self.last_answer = ""
        self.last_tool_count = 0
        self.repeated_answers = 0

    async def request(self, method, path, **kwargs):
        response = await self.client.request(
            method, path, headers={"x-static-client": "web"}, **kwargs
        )
        response.raise_for_status()
        return response.json()

    def remember_session(self):
        """Persist only the conversation ID, never API keys or message contents."""
        if self.conversation_id:
            target = self.data_dir / ".static-code-last-session"
            temporary = target.with_suffix(".tmp")
            temporary.write_text(self.conversation_id + "\n", encoding="utf-8")
            temporary.replace(target)

    async def setup(self):
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.completion import WordCompleter
            from prompt_toolkit.history import FileHistory
            from prompt_toolkit.styles import Style
        except ImportError as exc:
            raise RuntimeError("Install the terminal UI with: pip install -e '.[code]'") from exc
        self.data_dir.mkdir(parents=True, exist_ok=True)
        history_path = self.data_dir / ".static-code-history"
        self.session = PromptSession(
            history=FileHistory(str(history_path)),
            completer=WordCompleter(COMMANDS, sentence=True),
            complete_while_typing=False,
            multiline=False,
            bottom_toolbar=lambda: (
                f" ◈ STATIC  ·  {self.project['title'][:24] if self.project else self.mode}"
                f"  ·  {self.conversation_id[:8] if self.conversation_id else '-'}"
                "  ·  /projects  /moneyfarm  /help "
            ),
            style=Style.from_dict(
                {
                    "bottom-toolbar": "bg:#111827 #b8d5f6",
                    "prompt": "bold #67d9ff",
                    "": "bg:#0c1220 #e7efff",
                }
            ),
        )
        if self.conversation_id:
            await self.request("GET", f"/api/conversations/{self.conversation_id}")
        else:
            # A running auto-resume project takes priority over the manual chat picker.
            project = self.journal.auto_resume()
            if project:
                try:
                    await self.request("GET", f"/api/conversations/{project['conversation_id']}")
                    self.project = project
                    self.conversation_id = project["conversation_id"]
                    show_event("saved", "Resuming project: " + project["title"])
                except httpx.HTTPStatusError:
                    self.journal.checkpoint(
                        project, status="paused", note="Conversation missing; cannot auto-resume"
                    )
            if not self.conversation_id:
                rows = await self.request("GET", "/api/conversations")
                selection = await choose_chat(rows) if sys.stdin.isatty() and rows else None
                if selection and selection != "__new__":
                    self.conversation_id = selection
                elif selection == "__new__":
                    self.conversation_id = (
                        await self.request(
                            "POST", "/api/conversations", json={"title": "Static Code"}
                        )
                    )["id"]
                else:
                    previous = self.data_dir / ".static-code-last-session"
                    if previous.is_file():
                        saved_id = previous.read_text(encoding="utf-8").strip()
                        if saved_id:
                            try:
                                saved = await self.request("GET", f"/api/conversations/{saved_id}")
                                self.conversation_id = saved_id
                                show_event(
                                    "saved", "Restored chat: " + str(saved.get("title", saved_id))
                                )
                            except httpx.HTTPStatusError as exc:
                                if exc.response.status_code != 404:
                                    raise
                    if not self.conversation_id:
                        self.conversation_id = (
                            await self.request(
                                "POST", "/api/conversations", json={"title": "Static Code"}
                            )
                        )["id"]
            if not self.project:
                self.project = next(
                    (
                        p
                        for p in self.journal.list()
                        if p.get("conversation_id") == self.conversation_id
                        and p.get("status") == "active"
                    ),
                    None,
                )
        self.remember_session()

    async def ask(self, message):
        if not self.project:
            show_bubble("You", message)
        run = await self.request(
            "POST",
            f"/api/conversations/{self.conversation_id}/chat",
            json={
                "message": message,
                "mode": self.mode,
                "attachments": self.pending_attachments,
                "unlimited_steps": self.continuous,
                **({"budget_usd": self.budget} if self.budget is not None else {}),
            },
        )
        self.pending_attachments = []
        self.active_run = run["id"]
        last, seen_approvals = 0, set()
        objective_complete = False
        self.last_answer = ""
        self.last_tool_count = 0
        seen_actions = []
        heartbeat = time.monotonic()
        try:
            while True:
                result = await self.request(
                    "GET", f"/api/runs/{self.active_run}", params={"after": last}
                )
                for event in result["events"]:
                    last = max(last, event["id"])
                    kind, data = event["kind"], event["data"]
                    if kind == "plan":
                        steps = data.get("steps", [])
                        show_event(
                            "plan", "Plan: " + " → ".join(x.get("title", "") for x in steps[:12])
                        )
                    elif kind == "tool_start":
                        self.last_tool_count += 1
                        seen_actions.append(str(data.get("name", "tool")))
                        show_event("tool", data.get("name", "tool"))
                    elif kind == "tool_done":
                        show_event("saved", str(data.get("name", "tool")) + " finished")
                    elif kind == "tool_error":
                        seen_actions.append("Error: " + str(data.get("error", ""))[:200])
                        show_event("error", data.get("error", ""))
                    elif kind == "artifact":
                        seen_actions.append("Saved " + str(data.get("name", "artifact")))
                        show_event("saved", data.get("name", "artifact"))
                    elif kind == "answer":
                        content = data.get("content", "")
                        self.last_answer = content
                        if "STATIC_OBJECTIVE_COMPLETE" in content:
                            objective_complete = True
                        show_bubble("Static", content)
                    elif kind == "error":
                        seen_actions.append("Run error: " + str(data.get("message", ""))[:300])
                        show_event("error", data.get("message", ""))
                for approval in result["approvals"]:
                    if approval["id"] in seen_approvals:
                        continue
                    seen_approvals.add(approval["id"])
                    # Moneyfarm never silently approves external actions, purchases,
                    # media costs, or untrusted MCP tool side effects.
                    allowed_auto = self.auto_approve and (
                        not self.project
                        or self.project.get("kind") != "moneyfarm"
                        or approval["tool"] == "code_write"
                    )
                    if allowed_auto:
                        show_event("saved", "Auto-approved: " + str(approval["tool"]))
                        answer = "yes"
                    else:
                        print(f"\nPermission: {approval['tool']}")
                        print(json.dumps(approval["args"], ensure_ascii=False, indent=2)[:2000])
                        answer = (
                            (await self.session.prompt_async("Allow once? [y/N] ")).strip().lower()
                        )
                    await self.request(
                        "POST",
                        f"/api/approvals/{approval['id']}",
                        json={"allow": answer in ("y", "yes")},
                    )
                if result["status"] in ("completed", "failed", "cancelled", "interrupted"):
                    if result["status"] != "completed":
                        print(f"Run {result['status']}: {result.get('error', '')}")
                    spent = float(result.get("spent") or 0)
                    self.continuous_spent += spent
                    if self.project:
                        self.journal.checkpoint(
                            self.project,
                            note=("; ".join(seen_actions[-8:]) or "Run " + result["status"]),
                            answer=self.last_answer,
                            spent=spent,
                        )
                    return (
                        "objective_complete"
                        if objective_complete and result["status"] == "completed"
                        else result["status"]
                    )
                if self.project and time.monotonic() - heartbeat >= 120:
                    self.journal.save(self.project)
                    heartbeat = time.monotonic()
                await asyncio.sleep(0.35)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self.request("POST", f"/api/runs/{self.active_run}/stop")
            print("\nRun stopped.")
            self.continuous = False
            if self.project:
                self.journal.checkpoint(
                    self.project, status="paused", note="User interrupted the active run"
                )
            return "cancelled"
        finally:
            self.active_run = None

    async def run_project(self, *, first=False):
        """Run the saved objective repeatedly, with bounded costs and restart checkpoints."""
        if not self.project:
            print("Select a project with /projects or create one with /project new.")
            return
        self.continuous = True
        self.conversation_id = self.project["conversation_id"]
        self.remember_session()
        previous_answer = ""
        while self.continuous and self.project.get("status") == "active":
            remaining = float(self.project.get("spending_cap", 10)) - float(
                self.project.get("spent", 0)
            )
            if remaining <= 0:
                show_event("error", "Project spending cap reached; use /project budget USD.")
                self.journal.checkpoint(
                    self.project, status="paused", note="Estimated API spending cap reached"
                )
                self.continuous = False
                break
            prior_budget = self.budget
            self.budget = min(
                prior_budget if prior_budget is not None else remaining,
                remaining,
                100.0,
            )
            try:
                status = await self.ask(self.journal.resume_prompt(self.project, first=first))
            finally:
                self.budget = prior_budget
            first = False
            if status == "objective_complete":
                self.journal.checkpoint(
                    self.project,
                    status="complete",
                    note="Agent reported goal complete; verify deliverables",
                )
                self.continuous = False
                show_event("saved", "Goal marked complete. Check the evidence.")
                break
            if status == "cancelled":
                self.continuous = False
                break
            if status != "completed":
                self.project["failures"] = self.project.get("failures", 0) + 1
                if self.project["failures"] >= 2:
                    self.journal.checkpoint(
                        self.project,
                        status="paused",
                        note="Paused after two failed or interrupted runs: " + status,
                    )
                    self.continuous = False
                    show_event("error", "Repeated failure; project saved and paused.")
                    break
                show_event("error", "Run failed; retrying from checkpoint once.")
                await asyncio.sleep(2)
                continue
            self.project["failures"] = 0
            reply = " ".join(self.last_answer.split())
            if reply and reply == previous_answer:
                self.repeated_answers += 1
            else:
                self.repeated_answers = 0
            previous_answer = reply
            if self.repeated_answers >= 2 or (
                not self.last_tool_count
                and any(
                    phrase in reply.lower()
                    for phrase in (
                        "awaiting your approval",
                        "need your approval",
                        "waiting for your",
                        "cannot proceed without",
                    )
                )
            ):
                self.journal.checkpoint(
                    self.project,
                    status="paused",
                    note="No further autonomous progress; human input or review is needed",
                )
                self.continuous = False
                show_event("error", "Paused rather than looping without progress.")
                break
            await asyncio.sleep(1)

    async def command(self, line):
        command, _, argument = line.partition(" ")
        argument = argument.strip()
        if command in ("/exit", "/quit"):
            return False
        if command == "/help":
            print("""Commands:
  /new                 Create a new saved conversation
  /sessions            List saved conversations\n  /save                Save current chat as the default for next launch
  /resume ID           Resume an existing conversation (ID or unique prefix)
  /history             Show messages in this conversation
  /mode economy|local  Switch model routing
  /setup               Configure provider and API key
  /models              Show models and test connectivity
  /mcp /media          Inspect integrations and media jobs
  /task-new            Create a saved task
  /task-start ID       Start a saved task
  /upload PATH         Upload a file to this conversation
  /settings            View current configuration (no secrets)
  /rename TITLE        Rename current conversation
  /download ID PATH    Save a generated artifact to a local file
  /task-done ID        Mark task completed
  /task-reopen ID      Reopen a task
  /media-refresh       Refresh media jobs
  /media-cancel ID     Cancel a media job
  /mcp-reload          Reload MCP connections
  /budget USD          Set the per-run budget
  /auto on|off         Auto-approve tool actions (HIGH RISK)
  /continuous on|off   Repeatedly work until stopped (API costs)
  /both on|off         Enable/disable continuous + auto together (HIGH RISK)
  /project new          Create and run a goal-based persistent project
  /projects             Show and select saved projects (arrow keys)
  /project ID           Resume the named saved project
  /project status       Show goal, spending, checkpoints and progress
  /project budget USD   Change project estimated API spending cap
  /project pause|done   Pause the project / mark it complete
  /goal TEXT            Change the project's original goal
  /pause                Pause continuous work and disable auto-resume
  /moneyfarm            Start/resume the $10 Minecraft-service project
  /moneyfarm off        Pause the moneyfarm and disable auto-start
  /extension            List available repo-local extensions
  /extension install ID Enable and load a reviewed extension's tools
  /extension disable ID Disable extension tools
  /extension info ID    Show extension capabilities and permissions
  /status              Show session and mode
  /tasks /skills /files  Inspect existing Static data
  /clear               Clear terminal display (does not erase messages)
  /exit                Quit
Use Esc+Enter to insert a newline. Up/Down recalls previous prompts.
Ctrl+C during a run stops it; approval prompts default to No.""")
        elif command == "/new":
            self.conversation_id = (
                await self.request("POST", "/api/conversations", json={"title": "Static Code"})
            )["id"]
            self.project = None
            self.remember_session()
            print("Created session:", self.conversation_id)
        elif command in ("/sessions", "/conversations"):
            rows = await self.request("GET", "/api/conversations")
            for row in rows[:50]:
                print(f"{row['id']}  {row['title']}")
        elif command == "/resume":
            rows = await self.request("GET", "/api/conversations")
            matches = [r for r in rows if r["id"].startswith(argument)] if argument else []
            if len(matches) != 1:
                print("Provide an unambiguous session ID from /sessions.")
            else:
                self.conversation_id = matches[0]["id"]
                self.project = next(
                    (
                        p
                        for p in self.journal.list()
                        if p.get("conversation_id") == self.conversation_id
                    ),
                    None,
                )
                self.remember_session()
                print("Resumed:", matches[0]["title"])
        elif command == "/save":
            self.remember_session()
            print("Chat saved. It will reopen automatically next time:", self.conversation_id)
        elif command == "/history":
            data = await self.request("GET", f"/api/conversations/{self.conversation_id}")
            for item in data["messages"]:
                print(f"\n{item['role']}: {item['content']}")
        elif command == "/mode":
            if argument in ("economy", "local"):
                self.mode = argument
                print("Mode:", self.mode)
            else:
                print("Choose /mode economy or /mode local")
        elif command == "/setup":
            if await asyncio.to_thread(configure, self.data_dir, self.config):
                print("Provider saved. Run /models to test.")
        elif command == "/models":
            data = await self.request("GET", "/api/settings")
            for model in data["settings"]["models"]:
                print(f"{model['id']}: {model['provider']} / {model['model']}")
                try:
                    result = await self.request("POST", f"/api/models/{model['id']}/test")
                    print("  Connection:", json.dumps(result, ensure_ascii=False)[:400])
                except httpx.HTTPStatusError as exc:
                    print("  Test failed:", exc.response.status_code)
        elif command == "/task-new":
            title = (await self.session.prompt_async("Task title: ")).strip()
            objective = (await self.session.prompt_async("Task objective: ")).strip()
            if title and objective:
                item = await self.request(
                    "POST",
                    "/api/tasks",
                    json={"title": title, "objective": objective, "category": "work"},
                )
                print("Task saved:", item["id"])
        elif command == "/task-start":
            if not argument:
                print("Use /tasks to find the task ID.")
            else:
                result = await self.request(
                    "POST", f"/api/tasks/{argument}/start", json={"mode": self.mode}
                )
                print("Task started:", result["id"], "(track via /tasks)")
        elif command in ("/projects", "/project"):
            if command == "/projects" or not argument or argument == "list":
                rows = self.journal.list()
                if not rows:
                    print("No saved projects. Run /project new.")
                else:
                    for p in rows:
                        print(
                            f"{p['id']}  [{p['status']}] {p['title']} "
                            f"(${float(p.get('spent', 0)):.2f}/"
                            f"${float(p.get('spending_cap', 10)):.2f})"
                        )
                    if sys.stdin.isatty():
                        selected = await choose_chat(rows)
                        if selected and selected != "__new__":
                            self.project = self.journal.load(selected)
                            self.conversation_id = self.project["conversation_id"]
                            self.remember_session()
                            if self.project["status"] == "active":
                                await self.run_project()
            elif argument == "new":
                title = (await self.session.prompt_async("Project title: ")).strip()
                objective = (await self.session.prompt_async("Project goal: ")).strip()
                if title and objective:
                    conversation = await self.request(
                        "POST", "/api/conversations", json={"title": title[:100]}
                    )
                    self.project = self.journal.create(
                        title,
                        objective,
                        conversation["id"],
                        spending_cap=self.continuous_limit,
                    )
                    self.conversation_id = conversation["id"]
                    self.remember_session()
                    await self.run_project(first=True)
            elif argument == "status":
                if self.project:
                    print(json.dumps(self.project, ensure_ascii=False, indent=2)[:14000])
                else:
                    print("No active project. Run /projects.")
            elif argument == "pause":
                if self.project:
                    self.journal.checkpoint(self.project, status="paused", note="Paused by user")
                    self.project["auto_resume"] = False
                    self.journal.save(self.project)
                    self.continuous = False
                    print("Project paused and saved.")
            elif argument == "done":
                if self.project:
                    self.journal.checkpoint(
                        self.project, status="complete", note="Marked complete by user"
                    )
                    self.continuous = False
            elif argument.startswith("budget "):
                if not self.project:
                    print("Select a project first.")
                else:
                    try:
                        cap = float(argument.split(None, 1)[1])
                        if not 0 < cap <= 1000:
                            raise ValueError()
                        self.project["spending_cap"] = cap
                        self.journal.save(self.project)
                        print(f"Project cap set to ${cap:.2f} (estimated).")
                    except ValueError:
                        print("Usage: /project budget USD (0–1000)")
            elif argument == "resume":
                if self.project:
                    self.project["status"] = "active"
                    self.journal.save(self.project)
                    await self.run_project()
            else:
                rows = [p for p in self.journal.list() if p["id"].startswith(argument)]
                if len(rows) != 1:
                    print("Use /projects to get an unambiguous project ID.")
                else:
                    self.project = rows[0]
                    self.conversation_id = self.project["conversation_id"]
                    self.remember_session()
                    if self.project["status"] != "complete":
                        self.project["status"] = "active"
                        self.journal.save(self.project)
                        await self.run_project()
                    else:
                        print("This project is marked complete. /project status shows results.")
        elif command == "/goal":
            if not self.project or not argument:
                print("Usage: /goal NEW OBJECTIVE (inside a project)")
            else:
                self.project["goal"] = argument[:12000]
                self.project["status"] = "active"
                self.journal.checkpoint(self.project, note="Goal updated by user")
                print("Original project goal updated and saved.")
        elif command == "/pause":
            self.continuous = False
            self.auto_approve = False
            if self.project:
                self.project["auto_resume"] = False
                self.journal.checkpoint(
                    self.project, status="paused", note="Paused by user; auto-resume disabled"
                )
            print("Continuous and auto-approval disabled. Project checkpoint saved.")
        elif command == "/extension":
            operation, _, target = argument.partition(" ")
            target = target.strip()
            if not argument or operation == "list":
                items = await self.request("GET", "/api/extensions")
                if not items:
                    print("No extensions found in the repository /extensions folder.")
                for item in items:
                    print(
                        f"{item['id']} · {item['name']} [{'enabled' if item['active'] else 'available'}] "
                        f"v{item['version']}\n  {item['description']}"
                    )
                print(
                    "Extensions are local Python code, not sandboxed. Only install trusted sources."
                )
            elif operation == "info" and target:
                items = await self.request("GET", "/api/extensions")
                matches = [
                    x
                    for x in items
                    if target.casefold() in (x["name"].casefold(), x["id"].casefold())
                ]
                if len(matches) != 1:
                    print("Unknown extension. Run /extension list.")
                else:
                    print(json.dumps(matches[0], indent=2, ensure_ascii=False))
            elif operation in ("install", "enable") and target:
                items = await self.request("GET", "/api/extensions")
                matches = [
                    x
                    for x in items
                    if target.casefold() in (x["id"].casefold(), x["name"].casefold())
                ]
                if len(matches) != 1:
                    print("Unknown extension. Run /extension list for its ID.")
                else:
                    item = matches[0]
                    print(
                        f"Enabling {item['name']} loads trusted-local Python with "
                        "your user account permissions. It is not sandboxed."
                    )
                    confirmation = (
                        await self.session.prompt_async(f"Type INSTALL {item['id']} to enable: ")
                    ).strip()
                    if confirmation == "INSTALL " + item["id"]:
                        result = await self.request(
                            "POST", "/api/extensions/" + quote(item["id"], safe="") + "/enable"
                        )
                        print(
                            f"Enabled {result['id']}; tools: " + ", ".join(result.get("tools", []))
                        )
                    else:
                        print("Extension installation cancelled.")
            elif operation == "disable" and target:
                result = await self.request(
                    "POST", "/api/extensions/" + quote(target, safe="") + "/disable"
                )
                print("Disabled:", result["id"])
            else:
                print(
                    "Use /extension list, /extension info ID, "
                    "/extension install ID or /extension disable ID."
                )
        elif command == "/moneyfarm":
            if argument == "off":
                self.continuous = False
                self.auto_approve = False
                for p in self.journal.list():
                    if p.get("kind") == "moneyfarm" and p.get("status") == "active":
                        p["auto_resume"] = False
                        self.journal.checkpoint(
                            p, status="paused", note="Moneyfarm stopped by user"
                        )
                print("Moneyfarm paused. It will not auto-start.")
            elif not argument:
                existing = next(
                    (
                        p
                        for p in self.journal.list()
                        if p.get("kind") == "moneyfarm" and p.get("status") != "complete"
                    ),
                    None,
                )
                if existing:
                    self.project = existing
                    self.project["status"] = "active"
                    self.project["auto_resume"] = True
                else:
                    conversation = await self.request(
                        "POST", "/api/conversations", json={"title": "Moneyfarm · First $10"}
                    )
                    self.project = self.journal.create(
                        "Moneyfarm · First $10",
                        MONEYFARM_GOAL,
                        conversation["id"],
                        kind="moneyfarm",
                        auto_resume=True,
                        spending_cap=self.continuous_limit,
                    )
                self.conversation_id = self.project["conversation_id"]
                self.remember_session()
                self.journal.save(self.project)
                self.auto_approve = True
                self.continuous = True
                show_event(
                    "saved",
                    "Moneyfarm activated. Local code writes may be auto-approved; "
                    "external actions and paid tools require review.",
                )
                await self.run_project(first=self.project.get("turns", 0) == 0)
            else:
                print("Usage: /moneyfarm [off]")
        elif command == "/upload":
            path = Path(argument).expanduser()
            if not path.is_file() or path.stat().st_size > 5_000_000:
                print("Select an existing file under 5 MB.")
            else:
                with path.open("rb") as handle:
                    result = await self.request(
                        "POST",
                        f"/api/conversations/{self.conversation_id}/upload",
                        files={"file": (path.name, handle)},
                    )
                if result.get("id"):
                    self.pending_attachments.append(result["id"])
                print("Uploaded and attached to next message:", result.get("id", result))
        elif command == "/settings":
            data = await self.request("GET", "/api/settings")
            print(json.dumps(data["settings"], indent=2, ensure_ascii=False))
        elif command == "/auto":
            if argument == "off":
                self.auto_approve = False
                print("Automatic approvals disabled.")
            elif argument == "on":
                print(
                    "DANGER: This bypasses every tool approval, including commands, edits, and browser actions."
                )
                print(
                    "Untrusted AI output could delete files, expose data, or perform unintended actions."
                )
                confirm = (await self.session.prompt_async("Type AUTO APPROVE to accept: ")).strip()
                if confirm == "AUTO APPROVE":
                    self.auto_approve = True
                    print("⚠ Automatic approvals enabled for this session.")
                else:
                    print("Cancelled.")
            else:
                print("Usage: /auto on|off")
        elif command == "/continuous":
            if argument == "off":
                self.continuous = False
                print("Continuous mode disabled.")
            elif argument == "on":
                print("WARNING: Repeated API calls can be expensive. Stop with Ctrl+C.")
                raw = (
                    await self.session.prompt_async("Total estimated API spend limit USD [10]: ")
                ).strip() or "10"
                try:
                    limit = float(raw)
                    if not 0 < limit <= 1000:
                        raise ValueError()
                except ValueError:
                    print("Enter a positive cap of at most $1000.")
                else:
                    confirm = (await self.session.prompt_async("Type CONTINUE to enable: ")).strip()
                    if confirm == "CONTINUE":
                        self.continuous_limit = limit
                        self.continuous_spent = 0.0
                        self.continuous = True
                        print("Continuous mode enabled; cap is based on estimated tracked costs.")
            else:
                print("Usage: /continuous on|off")
        elif command == "/both":
            if argument == "off":
                self.continuous = False
                self.auto_approve = False
                print("Continuous mode and automatic approvals disabled.")
            elif argument == "on":
                print(
                    "DANGER: This enables unlimited-step continuous execution AND "
                    "automatic approval of commands, file edits, and browser actions."
                )
                print(
                    "The AI can make repeated changes without asking. API costs may "
                    "accumulate; estimated limits are not guaranteed billing caps."
                )
                raw = (
                    await self.session.prompt_async("Total estimated API spend limit USD [10]: ")
                ).strip() or "10"
                try:
                    limit = float(raw)
                    if not 0 < limit <= 1000:
                        raise ValueError()
                except ValueError:
                    print("Cancelled. Enter a positive cap of at most $1000.")
                else:
                    confirm = (
                        await self.session.prompt_async("Type ENABLE BOTH to accept: ")
                    ).strip()
                    if confirm == "ENABLE BOTH":
                        self.continuous_limit = limit
                        self.continuous_spent = 0.0
                        self.auto_approve = True
                        self.continuous = True
                        print("Both modes enabled for this session. Ctrl+C stops active runs.")
                    else:
                        print("Cancelled; neither setting was changed.")
            else:
                print("Usage: /both on|off")
        elif command == "/budget":
            try:
                amount = float(argument)
                if not 0 <= amount <= 100:
                    raise ValueError()
                self.budget = amount
                print(f"Per-run budget: ${amount:.2f}")
            except ValueError:
                print("Usage: /budget USD (0–100)")
        elif command == "/rename":
            if argument:
                await self.request(
                    "PATCH",
                    f"/api/conversations/{self.conversation_id}",
                    json={"title": argument[:100]},
                )
                print("Conversation renamed.")
            else:
                print("Usage: /rename TITLE")
        elif command == "/download":
            artifact_id, sep, destination = argument.partition(" ")
            if not sep or not destination:
                print("Usage: /download ARTIFACT_ID DESTINATION")
            else:
                target = Path(destination).expanduser().resolve()
                if target.exists():
                    print("Destination already exists; refusing to overwrite.")
                else:
                    response = await self.client.get(f"/api/artifacts/{artifact_id}/download")
                    response.raise_for_status()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as handle:
                        handle.write(response.content)
                    print("Saved:", target)
        elif command in ("/task-done", "/task-reopen"):
            if argument:
                status = "done" if command == "/task-done" else "open"
                await self.request("PATCH", f"/api/tasks/{argument}", json={"status": status})
                print("Task:", status)
            else:
                print("Usage:", command, "TASK_ID")
        elif command == "/media-refresh":
            print(json.dumps(await self.request("POST", "/api/media/refresh"), indent=2))
        elif command == "/media-cancel":
            if argument:
                print(
                    json.dumps(
                        await self.request("POST", f"/api/media/{argument}/cancel"), indent=2
                    )
                )
            else:
                print("Usage: /media-cancel JOB_ID")
        elif command == "/mcp-reload":
            print(json.dumps(await self.request("POST", "/api/mcp/reload"), indent=2))
        elif command == "/status":
            print(f"Session: {self.conversation_id}\nMode: {self.mode}\nData: {self.data_dir}")
            print(f"Continuous: {self.continuous}  Auto: {self.auto_approve}")
            if self.project:
                print(f"Project: {self.project['title']} [{self.project['status']}]")
                print(f"Goal: {self.project['goal'][:700]}")
                print(f"Estimated spent: ${float(self.project.get('spent', 0)):.2f}")
        elif command == "/clear":
            print("\033[2J\033[H", end="")
        elif command in ("/tasks", "/skills", "/files", "/mcp", "/media"):
            endpoint = {
                "/tasks": "/api/tasks",
                "/skills": "/api/skills",
                "/files": "/api/artifacts",
                "/mcp": "/api/mcp",
                "/media": "/api/media",
            }[command]
            print(json.dumps(await self.request("GET", endpoint), indent=2, ensure_ascii=False))
        else:
            print("Unknown command. Use /help.")
        return True

    async def loop(self, prompt=None):
        await self.setup()
        show_banner()
        if prompt is not None:
            await self.ask(prompt)
            return
        if (
            self.project
            and self.project.get("auto_resume")
            and (self.project.get("status") == "active")
        ):
            if self.project.get("kind") == "moneyfarm":
                self.auto_approve = True
            show_event("saved", "Auto-resuming goal: " + self.project["title"])
            await self.run_project()
        while True:
            try:
                line = (await self.session.prompt_async("❯ ")).strip()
                if not line:
                    continue
                if line.startswith("/"):
                    if not await self.command(line):
                        return
                elif self.continuous:
                    if not self.project:
                        self.project = self.journal.create(
                            line[:70],
                            line,
                            self.conversation_id,
                            spending_cap=self.continuous_limit,
                        )
                        await self.run_project(first=True)
                    else:
                        self.journal.checkpoint(self.project, note="User direction: " + line[:700])
                        await self.ask(line)
                        if self.project["status"] == "active":
                            await self.run_project()
                else:
                    await self.ask(line)
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye. Saved sessions remain on disk.")
                return
            except httpx.HTTPStatusError as exc:
                show_event("error", "Request failed: " + exc.response.text[:1000])


async def run(args):
    from .config import Config

    load_credentials(args.data_dir)
    config = Config(Path(args.data_dir))
    if not config.path.exists() and not os.getenv("STATIC_CHAT_MODEL"):
        if not sys.stdin.isatty():
            raise RuntimeError("First run requires an interactive terminal for provider setup.")
        print("Welcome to Static Code. Choose your AI provider before chatting.")
        if not await asyncio.to_thread(configure, args.data_dir, config):
            raise RuntimeError("No provider configured. Relaunch to finish setup.")
    app = create_app(args.data_dir)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost", timeout=30
        ) as client:
            terminal = Terminal(client, args.data_dir, args.mode, args.conversation)
            terminal.config = app.state.config
            await terminal.loop(args.prompt)


def main():
    from dotenv import load_dotenv

    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Static Code interactive terminal")
    parser.add_argument("--data-dir", default=os.getenv("STATIC_DATA_DIR", "data"))
    parser.add_argument("--conversation", help="Resume a saved conversation ID")
    parser.add_argument("--mode", choices=("economy", "local"), default="economy")
    parser.add_argument("-p", "--prompt", help="Run one prompt and exit")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except RuntimeError as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
