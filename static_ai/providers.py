"""Model routing across AI sources; no SDK lock-in or hidden fallback charges.

Every source speaks OpenAI-format messages to the engine: OpenAI-compatible servers natively,
the Anthropic Messages API and Claude Code through small adapters below.
"""

import json
import math
import os

import httpx

from . import claude_code
from .config import Model
from .db import uid

ANTHROPIC_VERSION = "2023-06-01"


def _tokens(prompt, completion):
    if isinstance(prompt, (int, float)) and isinstance(completion, (int, float)):
        return max(0, prompt), max(0, completion)
    return None


def anthropic_messages(messages):
    """OpenAI-format history -> (system, Anthropic messages) with tool_use/tool_result blocks."""
    system, out = [], []

    def add(role, blocks):
        # Anthropic expects alternating turns; all results for one tool turn share a user turn.
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for m in messages:
        if m["role"] == "system":
            system.append(m["content"])
        elif m["role"] == "tool":
            add(
                "user",
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": m.get("content") or "(empty)",
                    }
                ],
            )
        else:
            blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
            for call in m.get("tool_calls") or []:
                try:
                    arguments = json.loads(call["function"].get("arguments") or "{}")
                except ValueError:
                    arguments = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["function"]["name"],
                        "input": arguments if isinstance(arguments, dict) else {},
                    }
                )
            add(m["role"], blocks or [{"type": "text", "text": "(empty)"}])
    if out and out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": [{"type": "text", "text": "(Earlier messages)"}]})
    return "\n\n".join(system), out


class Providers:
    def __init__(self, config, store, transport=None):
        self.config, self.store, self.transport = config, store, transport

    def available(self, m):
        if m.provider == "claude_code":
            return claude_code.located() and (not m.key_env or bool(os.getenv(m.key_env)))
        return m.local or not m.key_env or bool(os.getenv(m.key_env))

    def choose(self, role, mode="economy", needs_tools=False):
        models = [
            m
            for m in self.config.settings.models
            if role in m.roles and (not needs_tools or m.tool_calling) and self.available(m)
        ]
        if mode == "local":
            models = [m for m in models if m.local]
        if not models:
            raise ValueError(
                f"No configured model is available for {role}. Check Settings and API keys."
            )
        return min(
            models, key=lambda m: (m.input_per_million + m.output_per_million * 2, not m.local)
        )

    async def complete(self, run_id, messages, role="coordinator", mode="economy", tools=None):
        model = self.choose(role, mode, bool(tools))
        # Byte count plus framing overhead deliberately overestimates ordinary tokenization.
        # Provider invoices remain authoritative; configured rates may be stale.
        input_bound = (
            len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode())
            + 512
        )
        if input_bound > 100_000:
            raise ValueError("Conversation context is full. Start a new chat with a short summary.")
        if model.provider == "claude_code":
            input_bound += claude_code.OVERHEAD_BYTES
        estimate = (
            input_bound * model.input_per_million
            + model.max_output_tokens * model.output_per_million
        ) / 1_000_000
        charge = self.store.reserve(
            run_id,
            math.ceil(estimate * 1_000_000) / 1_000_000,
            f"model:{model.id}",
            self.config.settings.daily_budget_usd,
        )
        self.store.event(
            run_id, "model", {"name": model.name, "role": role, "reserved_usd": estimate}
        )
        adapter = {"anthropic": self._anthropic, "claude_code": self._claude_code}.get(
            model.provider, self._openai
        )
        # On failure the reservation is retained: billing may be uncertain.
        reply, usage = await adapter(model, messages, tools)
        if usage:
            self.store.settle(
                charge,
                (usage[0] * model.input_per_million + usage[1] * model.output_per_million)
                / 1_000_000,
            )
        else:
            self.store.settle(charge)
        return reply

    def _headers(self, model):
        key = os.getenv(model.key_env, "") if model.key_env else ""
        if model.provider == "anthropic":
            return {"anthropic-version": ANTHROPIC_VERSION, **({"x-api-key": key} if key else {})}
        return {"Authorization": f"Bearer {key}"} if model.key_env else {}

    def _secrets(self):
        """Static's own credentials, hidden from the Claude Code child process."""
        return {m.key_env for m in self.config.settings.models if m.key_env} | {
            "BRAVE_API_KEY",
            "REPLICATE_API_TOKEN",
        }

    async def _post(self, model, path, payload):
        try:
            async with httpx.AsyncClient(
                timeout=180, transport=self.transport, trust_env=False
            ) as client:
                response = await client.post(
                    model.base_url.rstrip("/") + path, json=payload, headers=self._headers(model)
                )
        except httpx.RequestError as exc:
            raise ValueError(
                f"Cannot reach {model.name}. Start Ollama or check the configured provider connection. The cost reservation is retained if billing is uncertain."
            ) from exc
        if response.status_code >= 400:
            # Do not echo provider responses (could include credentials or private prompts).
            raise ValueError(
                f"{model.name} returned HTTP {response.status_code}. Check its model name, credentials and tool support."
            )
        return response.json()

    async def _openai(self, model, messages, tools):
        payload = {
            "model": model.model,
            "messages": messages,
            "stream": False,
            model.token_parameter: model.max_output_tokens,
        }
        if tools:
            payload["tools"] = tools
        result = await self._post(model, "/chat/completions", payload)
        usage = result.get("usage") or {}
        msg = result["choices"][0]["message"]
        # Do not persist provider-private reasoning fields.
        out = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            out["tool_calls"] = msg["tool_calls"]
        return out, _tokens(usage.get("prompt_tokens"), usage.get("completion_tokens"))

    async def _anthropic(self, model, messages, tools):
        system, converted = anthropic_messages(messages)
        payload = {"model": model.model, "max_tokens": model.max_output_tokens}
        if system:
            payload["system"] = system
        payload["messages"] = converted
        if tools:
            payload["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"],
                }
                for t in tools
            ]
        result = await self._post(model, "/messages", payload)
        text, calls = [], []
        # Only text and tool requests are kept; thinking and other blocks are not persisted.
        for block in result.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                text.append(block["text"])
            elif block.get("type") == "tool_use":
                calls.append(
                    {
                        "id": block.get("id") or uid(),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                        },
                    }
                )
        out = {"role": "assistant", "content": "\n\n".join(text)}
        if calls:
            out["tool_calls"] = calls
        usage = result.get("usage") or {}
        prompt = usage.get("input_tokens")
        if isinstance(prompt, (int, float)):
            # Cache writes and reads are counted at the full input rate: an overestimate.
            prompt += sum(
                usage.get(k) or 0
                for k in ("cache_creation_input_tokens", "cache_read_input_tokens")
            )
        return out, _tokens(prompt, usage.get("output_tokens"))

    async def _claude_code(self, model, messages, tools):
        system, prompt, schema = claude_code.request(messages, tools)
        data = await claude_code.run(
            model, system, prompt, schema, claude_code.child_env(model, self._secrets())
        )
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("input_tokens")
        if isinstance(prompt_tokens, (int, float)):
            prompt_tokens += sum(
                usage.get(k) or 0
                for k in ("cache_creation_input_tokens", "cache_read_input_tokens")
            )
        return claude_code.reply(data, tools), _tokens(prompt_tokens, usage.get("output_tokens"))

    async def health(self, model: Model):
        if model.provider == "claude_code":
            return await claude_code.health(model, claude_code.child_env(model, self._secrets()))
        anthropic = model.provider == "anthropic"
        try:
            async with httpx.AsyncClient(
                timeout=8, transport=self.transport, trust_env=False
            ) as client:
                r = await client.get(
                    model.base_url.rstrip("/") + "/models",
                    headers=self._headers(model),
                    params={"limit": 1000} if anthropic else None,
                )
                r.raise_for_status()
                names = [m["id"] for m in r.json().get("data", [])]
            # Anthropic lists dated IDs; an alias such as claude-x-1 matches claude-x-1-2025….
            listed = model.model in names or (
                anthropic and any(n.startswith(model.model + "-") for n in names)
            )
            return {
                "ok": listed,
                "models": names,
                "message": "Connected"
                if listed
                else "Connected, but the selected model was not listed",
            }
        except (httpx.HTTPError, ValueError, KeyError):
            return {
                "ok": False,
                "models": [],
                "message": "Connection failed. Check the endpoint, API key, and running model server.",
            }
