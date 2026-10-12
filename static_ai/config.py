"""Operator-owned settings. Secrets stay in environment variables, never in the UI."""

import json
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


def env(name, default=""):
    """Keep existing installations protected during the brand migration."""
    return os.getenv("STATIC_" + name, os.getenv("BUNS_" + name, default))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama")
# Where each source kind starts; operators can still point openai/anthropic at compatible servers.
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "claude_code": "",
}


def check_endpoint(url, local):
    """Shared rules for operator-configured HTTP endpoints (models and MCP servers)."""
    u = urlsplit(url)
    if (
        u.scheme not in ("https", "http")
        or not u.hostname
        or u.username
        or u.password
        or u.query
        or u.fragment
    ):
        raise ValueError("Use an HTTP(S) API base URL without credentials or query strings")
    if not local and u.scheme != "https":
        raise ValueError("Cloud endpoints must use HTTPS")
    if local and u.hostname not in LOCAL_HOSTS:
        raise ValueError("Local models must use a local host; mark remote servers as cloud")


class Model(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    name: str = Field(min_length=1, max_length=120)
    # openai: any OpenAI-compatible /chat/completions server. anthropic: the Claude Messages API.
    # claude_code: the operator's installed Claude Code CLI, run with its own tools turned off.
    provider: Literal["openai", "anthropic", "claude_code"] = "openai"
    model: str = Field(min_length=1, max_length=200)
    base_url: str = "http://localhost:11434/v1"
    key_env: str = Field(default="", pattern=r"^[A-Z0-9_]*$")
    input_per_million: float = Field(default=0, ge=0, le=10000)
    output_per_million: float = Field(default=0, ge=0, le=10000)
    local: bool = True
    pricing_confirmed: bool = False
    tool_calling: bool = True
    roles: list[Literal["coordinator", "researcher", "writer", "coder", "planner"]] = Field(
        default_factory=lambda: ["coordinator", "researcher", "writer", "coder", "planner"]
    )
    max_output_tokens: int = Field(default=2048, ge=256, le=8192)
    token_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"

    @model_validator(mode="after")
    def endpoint(self):
        if self.provider == "claude_code":
            # The model name becomes a CLI argument: allow aliases and model names, never flags.
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:\[\]-]{0,199}", self.model):
                raise ValueError(
                    "Use a Claude Code model alias such as sonnet or opus, or a full model name"
                )
            if self.local:
                raise ValueError(
                    "Claude Code sends prompts to Anthropic. Set it up as cloud and confirm pricing (0 if your plan covers it)"
                )
            self.base_url = ""
        else:
            check_endpoint(self.base_url, self.local)
        if not self.local and not self.pricing_confirmed:
            raise ValueError(
                "Confirm current provider pricing before enabling a cloud model (including free endpoints)"
            )
        if self.local and self.model.lower().endswith("cloud"):
            raise ValueError(
                "Cloud models served through Ollama must be configured as cloud, with pricing"
            )
        if self.local and (self.input_per_million or self.output_per_million):
            raise ValueError("Local models must have zero API pricing")
        return self


class MediaProfile(StrictModel):
    # Operator selects and reviews the provider's model schema and price.
    model: str = Field(default="", max_length=240)
    prompt_field: str = Field(default="prompt", pattern=r"^[a-zA-Z0-9_]{1,80}$")
    inputs: dict = Field(default_factory=dict)
    reserve_usd: float = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_model(self):
        if self.model and not re.fullmatch(r"[\w.-]+/[\w.-]+(?::[a-f0-9]{64})?", self.model):
            raise ValueError("Use owner/model or owner/model:64-character-version")
        if self.model and self.reserve_usd <= 0:
            raise ValueError("Set a conservative media cost reservation before enabling a model")
        if len(json.dumps(self.inputs)) > 16000:
            raise ValueError("Media defaults are too large")
        return self


class Settings(StrictModel):
    display_name: str = Field(default="", max_length=80)
    preferences: str = Field(default="", max_length=3000)
    models: list[Model] = Field(
        default_factory=lambda: [Model(id="local", name="Ollama · Qwen 3", model="qwen3:4b")],
        min_length=1,
        max_length=20,
    )
    daily_budget_usd: float = Field(default=2, ge=0, le=1000)
    run_budget_usd: float = Field(default=0.25, ge=0, le=100)
    max_steps: int = Field(default=12, ge=1, le=30)
    search_provider: Literal["duckduckgo", "brave"] = "duckduckgo"
    search_reserve_usd: float = Field(default=0.01, ge=0, le=1)
    media: dict[Literal["image", "video", "3d"], MediaProfile] = Field(
        default_factory=lambda: {k: MediaProfile() for k in ("image", "video", "3d")}
    )
    # Room for built-in skills plus individually disabled MCP tools.
    disabled_skills: list[str] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique_models(self):
        if len({m.id for m in self.models}) != len(self.models):
            raise ValueError("Model IDs must be unique")
        if not any(m.tool_calling and "coordinator" in m.roles for m in self.models):
            raise ValueError("At least one coordinator must support tool calling")
        return self


class Config:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "settings.json"
        if self.path.exists():
            self.settings = Settings.model_validate_json(self.path.read_text())
        elif env("CHAT_MODEL"):
            # Explicit first-run API configuration. Never infer a model or its price from a key.
            provider = env("CHAT_PROVIDER", "openai")
            if provider not in DEFAULT_BASE_URLS:
                raise ValueError("STATIC_CHAT_PROVIDER must be openai, anthropic or claude_code")
            # Claude Code uses its own sign-in unless a key variable is named explicitly.
            default_key = "" if provider == "claude_code" else "STATIC_API_KEY"
            model = Model(
                id="api",
                name=env("CHAT_NAME", "API model"),
                provider=provider,
                model=env("CHAT_MODEL"),
                base_url=env("CHAT_BASE_URL", DEFAULT_BASE_URLS[provider]),
                key_env=env("CHAT_KEY_ENV", default_key),
                local=False,
                pricing_confirmed=env("CHAT_PRICING_CONFIRMED").lower() == "true",
                input_per_million=float(env("CHAT_INPUT_PER_MILLION", "0")),
                output_per_million=float(env("CHAT_OUTPUT_PER_MILLION", "0")),
            )
            if model.key_env and not os.getenv(model.key_env):
                raise ValueError(f"Set {model.key_env} for the API model")
            if not model.key_env and provider != "claude_code":
                raise ValueError("Set STATIC_CHAT_KEY_ENV for the API model")
            self.settings = Settings(models=[model])
        else:
            self.settings = Settings()

    def save(self, settings: Settings):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(self.path)
        self.settings = settings

    def public(self):
        from .claude_code import located

        def ready(m):
            if m.provider == "claude_code":
                return located() and (not m.key_env or bool(os.getenv(m.key_env)))
            return bool(os.getenv(m.key_env)) if m.key_env else m.local

        data = self.settings.model_dump()
        return {
            "settings": data,
            "keys": {
                "brave": bool(os.getenv("BRAVE_API_KEY")),
                "replicate": bool(os.getenv("REPLICATE_API_TOKEN")),
                **{m.id: ready(m) for m in self.settings.models},
            },
        }
