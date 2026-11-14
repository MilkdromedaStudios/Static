"""Explicit, local-only Static extension loader.

An extension is a reviewed folder inside the repository's /extensions directory
with manifest.json and a Python entrypoint. Installation/enablement is explicit.
Extensions are executable Python with the same privileges as Static, NOT a
sandbox; never silently download or auto-execute third-party scripts.
"""

import importlib.util
import json
import os
import re
from pathlib import Path

from .skills.base import Registry


class ExtensionManager:
    def __init__(self, data_dir, repository_root=None):
        self.root = (
            Path(repository_root) if repository_root else Path(__file__).resolve().parent.parent
        ).resolve() / "extensions"
        self.root = self.root.resolve()
        self.state_file = Path(data_dir).resolve() / "extensions-enabled.json"
        self._loaded = {}
        self._enabled = self._read_enabled()
        for extension_id in sorted(self._enabled):
            # A broken extension must not prevent Static itself from starting.
            try:
                self._load(extension_id)
            except (ValueError, OSError, ImportError, AttributeError):
                pass

    def _read_enabled(self):
        try:
            value = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(value, list) and all(isinstance(x, str) for x in value):
                return set(value)
        except (FileNotFoundError, OSError, ValueError):
            pass
        return set()

    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(sorted(self._enabled), stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.state_file)
        finally:
            tmp.unlink(missing_ok=True)

    def discover(self):
        if not self.root.is_dir():
            return []
        results = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or directory.is_symlink():
                continue
            manifest_path = directory / "manifest.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            try:
                metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
                extension_id = metadata["id"]
                entrypoint = metadata["entrypoint"]
                if not isinstance(extension_id, str) or not re.fullmatch(
                    r"[a-z][a-z0-9-]{1,62}", extension_id
                ):
                    continue
                if not isinstance(entrypoint, str) or not re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]*\\.py", entrypoint
                ):
                    continue
                entry = (directory / entrypoint).resolve()
                if not entry.is_relative_to(directory.resolve()) or not entry.is_file():
                    continue
                results.append(
                    {
                        "id": extension_id,
                        "name": str(metadata.get("name", extension_id))[:100],
                        "description": str(metadata.get("description", ""))[:600],
                        "version": str(metadata.get("version", "0"))[:30],
                        "path": str(directory),
                        "entrypoint": str(entry),
                        "installed": extension_id in self._enabled,
                        "active": extension_id in self._loaded,
                        "note": "Local Python code. Only enable extensions you trust.",
                    }
                )
            except (ValueError, OSError, TypeError, KeyError):
                continue
        return results

    def _resolve(self, extension_id):
        matches = [
            item
            for item in self.discover()
            if extension_id.lower() in (item["id"].lower(), item["name"].lower())
        ]
        if len(matches) != 1:
            raise ValueError("Unknown or ambiguous extension. Use /extension list.")
        return matches[0]

    def _load(self, extension_id):
        item = self._resolve(extension_id)
        extension_id = item["id"]
        spec = importlib.util.spec_from_file_location(
            "static_extension_" + extension_id.replace("-", "_"), item["entrypoint"]
        )
        if spec is None or spec.loader is None:
            raise ValueError("The extension does not have a valid Python entrypoint")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "register"):
            raise ValueError("Extension must expose register(registry)")
        registry = Registry()
        module.register(registry)
        tools = list(registry.builtin.values())
        for tool in tools:
            if not tool.name.startswith(extension_id.replace("-", "_") + "_"):
                raise ValueError("Extension tools must use their extension ID as prefix")
            tool.source = "extension:" + extension_id
        self._loaded[extension_id] = tools

    def enable(self, extension_id):
        item = self._resolve(extension_id)
        if item["id"] not in self._loaded:
            self._load(item["id"])
        self._enabled.add(item["id"])
        self._save()
        return {
            "id": item["id"],
            "enabled": True,
            "tools": [skill.name for skill in self._loaded[item["id"]]],
        }

    def disable(self, extension_id):
        item = self._resolve(extension_id)
        self._enabled.discard(item["id"])
        self._loaded.pop(item["id"], None)
        self._save()
        return {"id": item["id"], "enabled": False}

    def skills(self):
        return [
            skill
            for ext_id, skills in self._loaded.items()
            if ext_id in self._enabled
            for skill in skills
        ]
