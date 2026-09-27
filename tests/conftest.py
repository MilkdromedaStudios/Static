import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from buns.app import create_app


class ScriptedProvider:
    def __init__(self):
        self.replies = []
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "qwen3:4b"}]})
        if request.url.path.endswith("/chat/completions"):
            answer = (
                self.replies.pop(0) if self.replies else {"role": "assistant", "content": "Done."}
            )
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": answer}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 30},
                },
            )
        if request.method == "POST" and request.url.path.endswith("/predictions"):
            return httpx.Response(201, json={"id": "prediction123", "status": "starting"})
        if request.method == "POST" and request.url.path.endswith("/cancel"):
            return httpx.Response(200, json={"status": "canceled"})
        if request.url.path.endswith("/predictions/prediction123"):
            return httpx.Response(
                200, json={"status": "succeeded", "output": ["https://cdn.example.com/test.png"]}
            )
        return httpx.Response(404)

    def tool(self, name, args):
        self.replies.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call{len(self.replies)}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ],
            }
        )


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("BUNS_ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")
    monkeypatch.delenv("BUNS_AUTH_TOKEN", raising=False)
    provider = ScriptedProvider()
    app = create_app(tmp_path, httpx.MockTransport(provider))
    with TestClient(app, headers={"X-Buns-Client": "web"}) as client:
        yield client, app, provider


def new_chat(client, message="Hello", **kwargs):
    conversation = client.post("/api/conversations", json={}).json()["id"]
    response = client.post(
        f"/api/conversations/{conversation}/chat", json={"message": message, **kwargs}
    )
    assert response.status_code == 202, response.text
    return conversation, response.json()["id"]


def wait_run(client, run, status=None):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get("/api/runs/" + run).json()
        if response["status"] == status or (
            status is None and response["status"] not in ("running", "queued")
        ):
            return response
        time.sleep(0.01)
    raise AssertionError(f"Run did not finish: {response}")
