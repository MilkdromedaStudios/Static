"""Test-only deterministic provider. Never imported by the production application."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from buns.app import create_app  # noqa: E402


def respond(request):
    if request.url.path.endswith("/models"):
        return httpx.Response(200, json={"data": [{"id": "qwen3:4b"}]})
    payload = json.loads(request.content)
    messages = payload["messages"]
    if messages[-1]["role"] == "tool":
        artifact = json.loads(messages[-1]["content"])
        content = f"Created your file: [{artifact['name']}]({artifact['url']})."
        message = {"role": "assistant", "content": content}
    else:
        message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "test-call",
                    "type": "function",
                    "function": {
                        "name": "file_create",
                        "arguments": json.dumps(
                            {
                                "name": "project-plan",
                                "format": "md",
                                "content": "# Project plan\n1. Research\n2. Build\n3. Review",
                            }
                        ),
                    },
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    )


if __name__ == "__main__":
    os.environ.pop("BUNS_AUTH_TOKEN", None)
    os.environ["BUNS_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    with tempfile.TemporaryDirectory(prefix="buns-ui-test-") as root:
        app = create_app(root, httpx.MockTransport(respond))
        uvicorn.run(app, host="127.0.0.1", port=8765)
