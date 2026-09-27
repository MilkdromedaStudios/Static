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


class Model(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    name: str = Field(min_length=1, max_length=120)
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
        u = urlsplit(self.base_url)
        if (
            u.scheme not in ("https", "http")
            or not u.hostname
            or u.username
            or u.password
            or u.query
            or u.fragment
        ):
            raise ValueError("Use an HTTP(S) API base URL without credentials or query strings")
        if not self.local and not self.pricing_confirmed:
            raise ValueError(
                "Confirm current provider pricing before enabling a cloud model (including free endpoints)"
            )
        if self.local and self.model.lower().endswith("cloud"):
            raise ValueError(
                "Cloud models served through Ollama must be configured as cloud, with pricing"
            )
        if not self.local and u.scheme != "https":
            raise ValueError("Cloud endpoints must use HTTPS")
        if self.local and u.hostname not in (
            "localhost",
            "127.0.0.1",
            "::1",
            "host.docker.internal",
            "ollama",
        ):
            raise ValueError("Local models must use a local host; mark remote servers as cloud")
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
    disabled_skills: list[str] = Field(default_factory=list, max_length=100)

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
        self.settings = (
            Settings.model_validate_json(self.path.read_text())
            if self.path.exists()
            else Settings()
        )

    def save(self, settings: Settings):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(self.path)
        self.settings = settings

    def public(self):
        data = self.settings.model_dump()
        return {
            "settings": data,
            "keys": {
                "brave": bool(os.getenv("BRAVE_API_KEY")),
                "replicate": bool(os.getenv("REPLICATE_API_TOKEN")),
                **{
                    m.id: bool(os.getenv(m.key_env)) if m.key_env else m.local
                    for m in self.settings.models
                },
            },
        }
