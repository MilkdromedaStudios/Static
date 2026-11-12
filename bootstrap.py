#!/usr/bin/env python3
"""Zero-dependency launcher: create/update a private venv and start Static Code.

Usage: python bootstrap.py [Static CLI options]
Python 3.11+ required. Internet is required only for first installation/updates.
"""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
MARKER = VENV / ".static-installed"


def python_path():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install(force=False):
    if sys.version_info < (3, 11):
        raise SystemExit("Static requires Python 3.11 or newer.")
    if not python_path().exists():
        print("[Static] Creating private Python environment...")
        venv.EnvBuilder(with_pip=True).create(VENV)
    if force or not MARKER.exists():
        print("[Static] Installing Python dependencies into .venv (first run may take a while)...")
        subprocess.run([str(python_path()), "-m", "pip", "install",
                        "--disable-pip-version-check", "--prefer-binary",
                        "-e", str(ROOT) + "[code]"], cwd=ROOT, check=True)
        MARKER.write_text("installed\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--update", action="store_true")
    args, passthrough = parser.parse_known_args()
    install(force=args.update)
    env = os.environ.copy()
    env.setdefault("STATIC_CODE_ROOT", os.getcwd())
    try:
        return subprocess.call([str(python_path()), "-m", "static_ai.terminal",
                                *passthrough], cwd=os.getcwd(), env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
