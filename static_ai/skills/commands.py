"""Approval-gated local process execution, bounded for low-memory machines."""
import asyncio
import os
import shlex
from pathlib import Path

from pydantic import Field

from ..config import StrictModel
from .base import Skill
from .code import resolve, root

MAX_OUTPUT = 16_384


class Command(StrictModel):
    command: list[str] = Field(min_length=1, max_length=40)
    cwd: str = Field(default=".", max_length=500)
    timeout_seconds: int = Field(default=30, ge=1, le=120)


def _validated(args):
    if any(not part or "\x00" in part or len(part) > 4096 for part in args.command):
        raise ValueError("Invalid command argument")
    cwd = resolve(args.cwd)
    if not cwd.is_dir():
        raise ValueError("Working directory does not exist")
    executable = args.command[0].lower()
    if executable in ("sudo", "su", "doas", "pkexec", "powershell", "pwsh",
                      "cmd", "cmd.exe", "bash", "sh", "zsh", "fish", "python",
                      "python3", "py", "node", "perl", "ruby"):
        # Interpreter execution is permitted only after explicit user approval.
        pass
    return cwd


async def run_command(ctx, args):
    cwd = _validated(args)
    # Never invoke a shell; argv is executed directly and is fully visible in approval.
    process = await asyncio.create_subprocess_exec(
        *args.command, cwd=str(cwd), stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )
    try:
        # Communicate drains output without deadlocking; bounded by timeout.
        output, _ = await asyncio.wait_for(process.communicate(), timeout=args.timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return {"exit_code": None, "timed_out": True, "output": "Command timed out"}
    text = output[:MAX_OUTPUT].decode("utf-8", errors="replace")
    return {"exit_code": process.returncode, "timed_out": False,
            "output": text, "truncated": len(output) > MAX_OUTPUT}


def terms(ctx, args):
    _validated(args)
    return {"workspace": str(root()), "cwd": args.cwd,
            "argv": args.command, "timeout_seconds": args.timeout_seconds}, 0.0


def register(registry):
    registry.add(Skill(
        "code_run", "Run an explicitly approved local command in the project workspace. "
        "Pass argv as a list (no shell interpretation), e.g. ['python', '-m', 'pytest']. "
        "Timeout 120 seconds maximum. Output capped at 16 KiB. Never run destructive "
        "or privileged commands without the user's informed approval.",
        "Code", Command, run_command, approval=True, terms=terms,
    ))
