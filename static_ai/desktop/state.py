"""Per-user desktop preferences, without provider secrets."""

import hashlib
import json
import os
import sys
from pathlib import Path

from pydantic import Field

from ..config import StrictModel

RELEASES_URL = "https://github.com/MilkdromedaStudios/Static/releases/latest"


class DesktopSettings(StrictModel):
    onboarded: bool = False
    minimize_to_tray: bool = True
    start_at_login: bool = False
    mini_on_top: bool = True
    server_port: int = Field(default=0, ge=0, le=65535)
    window_width: int = Field(default=1280, ge=800, le=4000)
    window_height: int = Field(default=850, ge=600, le=2400)


def default_data_dir():
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            raise RuntimeError("Windows did not provide your local application data folder.")
        return Path(root) / "StaticAI"
    return Path.home() / ".local" / "share" / "static-ai"


def instance_name(root):
    digest = hashlib.sha256(str(Path(root).resolve()).lower().encode()).hexdigest()[:24]
    return "static-ai-" + digest


def read_preferences(root):
    path = Path(root) / "desktop.json"
    if not path.exists():
        return DesktopSettings()
    return DesktopSettings.model_validate_json(path.read_text(encoding="utf-8"))


def save_preferences(root, settings):
    path = Path(root) / "desktop.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def set_login_start(enabled):
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        if enabled:
            raise RuntimeError("Start at login is available in the installed Windows app.")
        return
    import winreg

    with winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
    ) as key:
        if enabled:
            winreg.SetValueEx(key, "StaticAI", 0, winreg.REG_SZ, f'"{sys.executable}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, "StaticAI")
            except FileNotFoundError:
                pass


def credential_names(root):
    path = Path(root) / "credential-names.json"
    if not path.exists():
        return []
    names = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ValueError("Invalid credential name index")
    return names
