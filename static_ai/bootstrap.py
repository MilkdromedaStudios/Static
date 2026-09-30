"""Optional first-run local model setup. The HTTP workspace can always start without it."""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

OLLAMA_URL = "http://127.0.0.1:11434/api/tags"
DOWNLOAD_URL = "https://ollama.com/download"


def _local_ollama_models(config):
    return [
        model.model
        for model in config.settings.models
        if model.local
        and urlsplit(model.base_url).hostname in ("127.0.0.1", "localhost")
        and urlsplit(model.base_url).port == 11434
    ]


def _installed_models():
    try:
        request = Request(OLLAMA_URL, headers={"Accept": "application/json"})
        with build_opener(ProxyHandler({})).open(request, timeout=1.5) as response:
            payload = json.load(response)
        return {item.get("name") or item.get("model") for item in payload.get("models", [])}
    except (OSError, URLError, ValueError, TypeError, KeyError):
        return None


def _ask(question):
    if sys.stdin is None or not sys.stdin.isatty():
        return False
    try:
        return input(question + " [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nSkipping setup.")
        return False


def _install_ollama():
    system = platform.system()
    if system == "Windows":
        if not shutil.which("winget"):
            print(f"Install Ollama from {DOWNLOAD_URL}, then restart Static.")
            return False
        command = [
            "winget",
            "install",
            "--id",
            "Ollama.Ollama",
            "--exact",
            "--source",
            "winget",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ]
    elif system == "Darwin":
        if not shutil.which("brew"):
            print(
                f"Install Ollama from {DOWNLOAD_URL}, then restart Static (or install Homebrew first)."
            )
            return False
        command = ["brew", "install", "ollama"]
    elif system == "Linux":
        if not shutil.which("curl"):
            print(f"Install Ollama from {DOWNLOAD_URL}, then restart Static.")
            return False
        with tempfile.NamedTemporaryFile(
            prefix="static-ollama-", suffix=".sh", delete=False
        ) as script:
            location = Path(script.name)
        try:
            download = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--location",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    "60",
                    "--output",
                    str(location),
                    "https://ollama.com/install.sh",
                ],
                check=False,
            )
            if download.returncode or not 0 < location.stat().st_size <= 2_000_000:
                print(f"Could not download the official installer. Use {DOWNLOAD_URL} instead.")
                return False
            command = ["sh", str(location)]
            return subprocess.run(command, check=False).returncode == 0
        finally:
            location.unlink(missing_ok=True)
    else:
        print(f"Install Ollama from {DOWNLOAD_URL}, then restart Static.")
        return False
    return subprocess.run(command, check=False).returncode == 0


def _ollama_binary():
    binary = shutil.which("ollama")
    if binary or os.name != "nt":
        return binary
    # WinGet can install Ollama without refreshing this process's PATH.
    for folder, suffix in (
        ("LOCALAPPDATA", "Programs/Ollama/ollama.exe"),
        ("ProgramFiles", "Ollama/ollama.exe"),
    ):
        root = os.environ.get(folder)
        if root and (candidate := Path(root) / suffix).is_file():
            return str(candidate)
    return None


def _launch_ollama(binary, data_dir):
    log_path = Path(data_dir) / "ollama.log"
    with log_path.open("ab") as log:
        options = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT}
        if os.name == "nt":
            options["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            options["start_new_session"] = True
        subprocess.Popen([binary, "serve"], **options)
    for _ in range(16):
        if _installed_models() is not None:
            print("Ollama is ready.")
            return True
        time.sleep(0.5)
    print(f"Ollama has not responded yet. Check {log_path} or start it manually.")
    return False


def ensure_local_model(config, ask=None):
    """Start the configured local Ollama service, offering official installers if absent.

    Server startup never depends on Ollama. API-key model configurations skip it entirely.
    Nothing is downloaded without an interactive yes at the relevant prompt.
    """
    ask = ask or _ask
    models = _local_ollama_models(config)
    if not models:
        return
    available = _installed_models()
    binary = _ollama_binary()
    if available is None:
        if not binary:
            print("Ollama is not installed. You can use API keys instead in Connections.")
            if not ask("Install Ollama for local AI using the official installer?"):
                return
            if not _install_ollama():
                print("Ollama installation did not finish; Static can still use API-key models.")
                return
            binary = _ollama_binary()
            available = _installed_models()
        if available is None:
            if not binary:
                print(
                    "Open Ollama, then restart Static (or configure an API-key model in Connections)."
                )
                return
            print("Starting Ollama in the background…")
            try:
                if not _launch_ollama(binary, config.root):
                    return
            except OSError as exc:
                print(f"Could not start Ollama: {exc}. Use an API-key model or start it manually.")
                return
            available = _installed_models()
    for model in set(models) - (available or set()):
        if not binary:
            print(
                f"Ollama is running, but {model} is missing. Install it with: ollama pull {model}"
            )
        elif ask(f"Download the local model {model}? This may use several GB of disk space"):
            result = subprocess.run([binary, "pull", model], check=False)
            if result.returncode:
                print(f"Model download did not finish. Retry with: ollama pull {model}")
        else:
            print(f"You can download it later with: ollama pull {model}")
