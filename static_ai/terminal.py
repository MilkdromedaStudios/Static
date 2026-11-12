"""Static Code: persistent, keyboard-first terminal interface.

The same application service powers the web UI and terminal; messages and runs
are saved in Static's SQLite workspace.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from .app import create_app
from .terminal_setup import configure, load_credentials

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

    async def request(self, method, path, **kwargs):
        response = await self.client.request(
            method, path, headers={"x-static-client": "web"}, **kwargs
        )
        response.raise_for_status()
        return response.json()

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
                f" Static Code | {self.mode} | session {self.conversation_id[:8] if self.conversation_id else '-'} | Enter send | Esc+Enter newline | /help "
            ),
            style=Style.from_dict({"bottom-toolbar": "bg:#303846 #ffffff"}),
        )
        if self.conversation_id:
            await self.request("GET", f"/api/conversations/{self.conversation_id}")
        else:
            self.conversation_id = (
                await self.request("POST", "/api/conversations", json={"title": "Static Code"})
            )["id"]

    async def ask(self, message):
        run = await self.request(
            "POST",
            f"/api/conversations/{self.conversation_id}/chat",
            json={
                "message": message,
                "mode": self.mode,
                **({"budget_usd": self.budget} if self.budget is not None else {}),
            },
        )
        self.pending_attachments = []
        self.active_run = run["id"]
        last, seen_approvals = 0, set()
        try:
            while True:
                result = await self.request(
                    "GET", f"/api/runs/{self.active_run}", params={"after": last}
                )
                for event in result["events"]:
                    last = max(last, event["id"])
                    kind, data = event["kind"], event["data"]
                    if kind == "tool_start":
                        print(f"  ⚙ {data.get('name', 'tool')}")
                    elif kind == "tool_error":
                        print(f"  Tool error: {data.get('error', '')}")
                    elif kind == "artifact":
                        print(f"  Saved: {data.get('name', 'artifact')}")
                    elif kind == "answer":
                        print("\nStatic:\n" + data.get("content", "") + "\n")
                    elif kind == "error":
                        print("Error:", data.get("message", ""), file=sys.stderr)
                for approval in result["approvals"]:
                    if approval["id"] in seen_approvals:
                        continue
                    seen_approvals.add(approval["id"])
                    print(f"\nPermission: {approval['tool']}")
                    print(json.dumps(approval["args"], ensure_ascii=False, indent=2)[:2000])
                    answer = (await self.session.prompt_async("Allow once? [y/N] ")).strip().lower()
                    await self.request(
                        "POST",
                        f"/api/approvals/{approval['id']}",
                        json={"allow": answer in ("y", "yes")},
                    )
                if result["status"] in ("completed", "failed", "cancelled", "interrupted"):
                    if result["status"] != "completed":
                        print(f"Run {result['status']}: {result.get('error', '')}")
                    return
                await asyncio.sleep(0.35)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self.request("POST", f"/api/runs/{self.active_run}/stop")
            print("\nRun stopped.")
        finally:
            self.active_run = None

    async def command(self, line):
        command, _, argument = line.partition(" ")
        argument = argument.strip()
        if command in ("/exit", "/quit"):
            return False
        if command == "/help":
            print("""Commands:
  /new                 Create a new saved conversation
  /sessions            List saved conversations
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
                print("Resumed:", matches[0]["title"])
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
        print("Static Code  •  /help commands  •  /sessions saved chats")
        if prompt is not None:
            await self.ask(prompt)
            return
        while True:
            try:
                line = (await self.session.prompt_async("❯ ")).strip()
                if not line:
                    continue
                if line.startswith("/"):
                    if not await self.command(line):
                        return
                else:
                    await self.ask(line)
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                return
            except httpx.HTTPStatusError as exc:
                print("Request failed:", exc.response.text[:1000], file=sys.stderr)


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
