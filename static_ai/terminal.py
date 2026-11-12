"""Interactive, local Static terminal client using the same engine and data as the web UI."""
import argparse
import asyncio
import json
import os
import shlex
import sys
from pathlib import Path

import httpx

from .app import Chat, Title, create_app


async def _request(client, method, path, **kwargs):
    response = await client.request(method, path, headers={"x-static-client": "web"}, **kwargs)
    response.raise_for_status()
    return response.json()


async def _run(client, conversation_id, message, mode):
    result = await _request(client, "POST", f"/api/conversations/{conversation_id}/chat",
                            json={"message": message, "mode": mode})
    run_id = result["id"]
    last = 0
    while True:
        result = await _request(client, "GET", f"/api/runs/{run_id}", params={"after": last})
        for event in result["events"]:
            last = max(last, event["id"])
            kind, data = event["kind"], event["data"]
            if kind == "tool_start":
                print(f"  [tool] {data.get('name')}")
            elif kind == "answer":
                print("\nStatic:", data.get("content", ""))
            elif kind == "error":
                print("Error:", data.get("message", ""), file=sys.stderr)
        for approval in result["approvals"]:
            print(f"Approval required: {approval['tool']} {json.dumps(approval['args'])[:600]}")
            answer = (await asyncio.to_thread(input, "Allow once? [y/N] ")).strip().lower()
            await _request(client, "POST", f"/api/approvals/{approval['id']}",
                           json={"allow": answer in ("y", "yes")})
        if result["status"] in ("completed", "failed", "cancelled", "interrupted"):
            if result["status"] != "completed":
                print(f"Run {result['status']}: {result.get('error', '')}")
            return
        await asyncio.sleep(0.3)


async def interactive(args):
    app = create_app(args.data_dir)
    # Run the actual Static backend in-process: no web server or browser UI needed.
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            conversations = await _request(client, "GET", "/api/conversations")
            conversation_id = args.conversation
            if conversation_id is None:
                conversation_id = (await _request(client, "POST", "/api/conversations",
                                                 json={"title": "Static CLI"}))["id"]
            mode = args.mode
            print("Static CLI | /help for commands | /exit to quit")
            if args.prompt:
                await _run(client, conversation_id, args.prompt, mode)
                return
            while True:
                try:
                    line = (await asyncio.to_thread(input, "static> ")).strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not line:
                    continue
                if line in ("/exit", "/quit"):
                    break
                if line == "/help":
                    print("/help /exit /new /conversations /tasks /skills /files /mode economy|local")
                    continue
                if line == "/new":
                    conversation_id = (await _request(client, "POST", "/api/conversations",
                                    json={"title": "Static CLI"}))["id"]
                    print("New conversation:", conversation_id)
                    continue
                if line.startswith("/mode "):
                    requested = line.split(maxsplit=1)[1]
                    if requested in ("economy", "local"):
                        mode = requested
                        print("Mode:", mode)
                    else:
                        print("Modes: economy, local")
                    continue
                endpoints = {"/conversations": "/api/conversations", "/tasks": "/api/tasks",
                             "/skills": "/api/skills", "/files": "/api/artifacts"}
                if line in endpoints:
                    print(json.dumps(await _request(client, "GET", endpoints[line]),
                                     indent=2, ensure_ascii=False))
                    continue
                try:
                    await _run(client, conversation_id, line, mode)
                except httpx.HTTPStatusError as exc:
                    print("Request failed:", exc.response.text[:500], file=sys.stderr)


def main():
    from dotenv import load_dotenv
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Interactive Static AI terminal")
    parser.add_argument("--data-dir", default=os.getenv("STATIC_DATA_DIR", "data"))
    parser.add_argument("--conversation", help="Resume an existing conversation ID")
    parser.add_argument("--mode", choices=["economy", "local"], default="economy")
    parser.add_argument("-p", "--prompt", help="Run one prompt and exit")
    args = parser.parse_args()
    asyncio.run(interactive(args))


if __name__ == "__main__":
    main()
