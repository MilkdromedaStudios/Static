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

COMMANDS = ("/help", "/exit", "/quit", "/new", "/resume", "/sessions",
            "/history", "/tasks", "/skills", "/files", "/mode", "/status", "/clear")


class Terminal:
    def __init__(self, client, data_dir, mode, conversation_id=None):
        self.client = client
        self.data_dir = Path(data_dir).resolve()
        self.mode = mode
        self.conversation_id = conversation_id
        self.session = None
        self.active_run = None

    async def request(self, method, path, **kwargs):
        response = await self.client.request(method, path,
            headers={"x-static-client": "web"}, **kwargs)
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
            bottom_toolbar=lambda: f" Static Code | {self.mode} | session {self.conversation_id[:8] if self.conversation_id else '-'} | Enter send | Esc+Enter newline | /help ",
            style=Style.from_dict({"bottom-toolbar": "bg:#303846 #ffffff"}),
        )
        if self.conversation_id:
            await self.request("GET", f"/api/conversations/{self.conversation_id}")
        else:
            self.conversation_id = (await self.request("POST", "/api/conversations",
                json={"title": "Static Code"}))["id"]

    async def ask(self, message):
        run = await self.request("POST",
            f"/api/conversations/{self.conversation_id}/chat",
            json={"message": message, "mode": self.mode})
        self.active_run = run["id"]
        last, seen_approvals = 0, set()
        try:
            while True:
                result = await self.request("GET", f"/api/runs/{self.active_run}",
                                            params={"after": last})
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
                    await self.request("POST", f"/api/approvals/{approval['id']}",
                                       json={"allow": answer in ("y", "yes")})
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
  /status              Show session and mode
  /tasks /skills /files  Inspect existing Static data
  /clear               Clear terminal display (does not erase messages)
  /exit                Quit
Use Esc+Enter to insert a newline. Up/Down recalls previous prompts.
Ctrl+C during a run stops it; approval prompts default to No.""")
        elif command == "/new":
            self.conversation_id = (await self.request("POST", "/api/conversations",
                json={"title": "Static Code"}))["id"]
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
        elif command == "/status":
            print(f"Session: {self.conversation_id}\nMode: {self.mode}\nData: {self.data_dir}")
        elif command == "/clear":
            print("\033[2J\033[H", end="")
        elif command in ("/tasks", "/skills", "/files"):
            endpoint = {"/tasks": "/api/tasks", "/skills": "/api/skills",
                        "/files": "/api/artifacts"}[command]
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
    app = create_app(args.data_dir)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://localhost", timeout=30) as client:
            terminal = Terminal(client, args.data_dir, args.mode, args.conversation)
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
