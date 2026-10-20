"""Test-only MCP server over stdio. Never imported by the production application.

Usage: python mcp_server.py LOG_PATH. Each tool call (and the server environment) is appended
to LOG_PATH as JSON lines so tests can prove what did, and did not, run.
"""

import base64
import json
import os
import sys

LOG = sys.argv[1]
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake-png-for-tests").decode()
TOOLS = [
    {
        "name": "echo",
        "title": "Echo",
        "description": "Repeat the given text.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "save.note",
        "description": "Save a note on the server.",
        "inputSchema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"note": {"type": "string"}},
        },
    },
    {
        "name": "fail",
        "description": "Always fails.",
        "inputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "picture",
        "description": "Return a small image.",
        "inputSchema": {"type": "object"},
        "annotations": {"readOnlyHint": True},
    },
]


def log(entry):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def call(name, arguments):
    log({"call": name, "arguments": arguments})
    if name == "echo":
        return {"content": [{"type": "text", "text": arguments["text"]}]}
    if name == "save.note":
        return {"content": [{"type": "text", "text": "Saved."}]}
    if name == "fail":
        return {"content": [{"type": "text", "text": "boom"}], "isError": True}
    return {"content": [{"type": "image", "data": PNG, "mimeType": "image/png"}]}


print("not json: servers sometimes log here", flush=True)
print("test server starting", file=sys.stderr, flush=True)
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    method, params = message["method"], message.get("params") or {}
    if method == "initialize":
        log({"env": sorted(os.environ), "greeting": os.environ.get("GREETING")})
        result = {
            "protocolVersion": params["protocolVersion"],
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "test-server", "version": "1.0"},
        }
    elif method == "tools/list":
        if params.get("cursor") == "page-2":
            result = {"tools": TOOLS[2:]}
        else:
            result = {"tools": TOOLS[:2], "nextCursor": "page-2"}
    elif method == "tools/call":
        result = call(params["name"], params.get("arguments") or {})
    else:
        reply = {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "?"}}
        print(json.dumps(reply), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
