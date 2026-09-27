"""OpenAI-compatible chat routing; no SDK lock-in or hidden fallback charges."""

import json
import math
import os

import httpx

from .config import Model


class Providers:
    def __init__(self, config, store, transport=None):
        self.config, self.store, self.transport = config, store, transport

    def choose(self, role, mode="economy", needs_tools=False):
        models = [
            m
            for m in self.config.settings.models
            if role in m.roles
            and (not needs_tools or m.tool_calling)
            and (m.local or not m.key_env or os.getenv(m.key_env))
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
        payload = {
            "model": model.model,
            "messages": messages,
            "stream": False,
            model.token_parameter: model.max_output_tokens,
        }
        if tools:
            payload["tools"] = tools
        # Byte count plus framing overhead deliberately overestimates ordinary tokenization.
        # Provider invoices remain authoritative; configured rates may be stale.
        input_bound = len(json.dumps(payload, ensure_ascii=False).encode()) + 512
        if input_bound > 100_000:
            raise ValueError("Conversation context is full. Start a new chat with a short summary.")
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
        headers = (
            {"Authorization": f"Bearer {os.getenv(model.key_env, '')}"} if model.key_env else {}
        )
        try:
            async with httpx.AsyncClient(
                timeout=180, transport=self.transport, trust_env=False
            ) as client:
                response = await client.post(
                    model.base_url.rstrip("/") + "/chat/completions", json=payload, headers=headers
                )
                if response.status_code >= 400:
                    # Do not echo provider responses (could include credentials or private prompts).
                    raise ValueError(
                        f"{model.name} returned HTTP {response.status_code}. Check its model name, credentials and tool support."
                    )
                result = response.json()
            usage = result.get("usage", {})
            if "prompt_tokens" in usage and "completion_tokens" in usage:
                amount = (
                    max(0, usage["prompt_tokens"]) * model.input_per_million
                    + max(0, usage["completion_tokens"]) * model.output_per_million
                ) / 1_000_000
                self.store.settle(charge, amount)
            else:
                self.store.settle(charge)
            msg = result["choices"][0]["message"]
            # Do not persist provider-private reasoning fields.
            out = {"role": "assistant", "content": msg.get("content") or ""}
            if msg.get("tool_calls"):
                out["tool_calls"] = msg["tool_calls"]
            return out
        except httpx.RequestError as exc:
            raise ValueError(
                f"Cannot reach {model.name}. Start Ollama or check the configured provider connection. The cost reservation is retained if billing is uncertain."
            ) from exc

    async def health(self, model: Model):
        headers = (
            {"Authorization": f"Bearer {os.getenv(model.key_env, '')}"} if model.key_env else {}
        )
        try:
            async with httpx.AsyncClient(
                timeout=8, transport=self.transport, trust_env=False
            ) as client:
                r = await client.get(model.base_url.rstrip("/") + "/models", headers=headers)
                r.raise_for_status()
                names = [m["id"] for m in r.json().get("data", [])]
            return {
                "ok": model.model in names,
                "models": names,
                "message": "Connected"
                if model.model in names
                else "Connected, but the selected model was not listed",
            }
        except (httpx.HTTPError, ValueError, KeyError):
            return {
                "ok": False,
                "models": [],
                "message": "Connection failed. Check the endpoint, API key, and running model server.",
            }
