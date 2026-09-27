"""Typed, explicit skill registry. Plugins are trusted Python code, not downloaded prompts."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel


@dataclass
class Context:
    run_id: str
    conversation_id: str
    mode: str
    store: Any
    config: Any
    providers: Any
    artifacts: Any
    media: Any


@dataclass
class Skill:
    name: str
    description: str
    category: str
    args: type[BaseModel]
    handler: Callable[[Context, Any], Awaitable[Any]]
    approval: bool = False

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args.model_json_schema(),
            },
        }


class Registry:
    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def add(self, skill: Skill):
        if skill.name in self.skills:
            raise ValueError(f"Duplicate skill: {skill.name}")
        self.skills[skill.name] = skill

    def enabled(self, config):
        return [s for s in self.skills.values() if s.name not in config.settings.disabled_skills]

    def schemas(self, config):
        return [s.schema() for s in self.enabled(config)]
