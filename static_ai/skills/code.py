"""Explicitly scoped source-code tools for Static Code.

Reads are restricted to STATIC_CODE_ROOT (defaults to current working directory).
Writes require one-use approval from the user, including the target path and content.
"""

import os
from pathlib import Path

from pydantic import Field

from ..config import StrictModel
from .base import Skill

MAX_READ = 120_000
MAX_WRITE = 120_000
SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".env"}


def root():
    return Path(os.getenv("STATIC_CODE_ROOT", os.getcwd())).resolve()


def resolve(path):
    base = root()
    target = (base / path).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Path must stay inside the configured workspace")
    if any(part in SKIP for part in target.relative_to(base).parts):
        raise ValueError("Protected or generated directory")
    return target


class PathArgs(StrictModel):
    path: str = Field(default=".", min_length=1, max_length=500)


class WriteArgs(StrictModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(max_length=MAX_WRITE)


async def list_source(ctx, args):
    target = resolve(args.path)
    if not target.is_dir():
        raise ValueError("Not a directory")
    entries = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    return {
        "workspace": str(root()),
        "path": args.path,
        "entries": [
            {"name": p.name, "type": "directory" if p.is_dir() else "file"}
            for p in entries
            if p.name not in SKIP and not p.is_symlink()
        ][:200],
    }


async def read_source(ctx, args):
    target = resolve(args.path)
    if not target.is_file() or target.stat().st_size > MAX_READ:
        raise ValueError("File missing or too large (120 KB max)")
    try:
        content = target.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise ValueError("File is not readable UTF-8 text") from exc
    return {"path": args.path, "content": content, "untrusted_file_content": True}


async def write_source(ctx, args):
    target = resolve(args.path)
    if target.exists() and not target.is_file():
        raise ValueError("Target is not a regular file")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement; preserve original if writing fails.
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=target.parent, prefix=".static-", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(args.content)
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": args.path, "bytes": len(args.content.encode("utf-8")), "written": True}


def write_terms(ctx, args):
    return {"workspace": str(root()), "path": args.path, "content": args.content}, 0.0


def register(registry):
    registry.add(
        Skill(
            "code_list",
            "List files in the configured local project workspace.",
            "Code",
            PathArgs,
            list_source,
        )
    )
    registry.add(
        Skill(
            "code_read",
            "Read a UTF-8 source file inside the configured project workspace.",
            "Code",
            PathArgs,
            read_source,
        )
    )
    registry.add(
        Skill(
            "code_write",
            "Create or replace a source file inside the configured project workspace. Requires explicit one-time approval for the exact file and content. Never modify secrets.",
            "Code",
            WriteArgs,
            write_source,
            approval=True,
            terms=write_terms,
        )
    )
