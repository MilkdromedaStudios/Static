"""Typed, explicit skill registry. Plugins are trusted Python code, not downloaded prompts.

Tools from operator-configured MCP servers join through `Registry.extend`; they are listed and
switched on/off like built-in skills.
"""

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
    # For approval skills: (ctx, args) -> (terms, cost). The one-use approval binds to these
    # terms, and the action is refused if they differ when the approved call runs.
    terms: Callable[[Context, Any], tuple[dict, float]] | None = None
    # JSON Schema supplied by an external tool source instead of the args model.
    parameters: dict | None = None
    title: str = ""
    source: str = ""

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or self.args.model_json_schema(),
            },
        }


class Registry:
    def __init__(self):
        self.builtin: dict[str, Skill] = {}
        self.sources: list[Callable[[], list[Skill]]] = []

    def add(self, skill: Skill):
        if skill.name in self.builtin:
            raise ValueError(f"Duplicate skill: {skill.name}")
        self.builtin[skill.name] = skill

    def extend(self, source: Callable[[], list[Skill]]):
        self.sources.append(source)

    @property
    def skills(self) -> dict[str, Skill]:
        merged = dict(self.builtin)
        for source in self.sources:
            for skill in source():
                merged.setdefault(skill.name, skill)
        return merged

    def enabled(self, config):
        return [s for s in self.skills.values() if s.name not in config.settings.disabled_skills]

    def schemas(self, config):
        return [s.schema() for s in self.enabled(config)]
