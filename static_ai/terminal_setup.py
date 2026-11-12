"""Interactive model setup for Static Code. No implicit model downloads.

Model settings use the same Config/Settings objects as the web app.
Credentials are stored in a private per-workspace dotenv file, never settings.json.
"""
import getpass
import os
from pathlib import Path

from dotenv import load_dotenv, set_key

from .config import Config, Model, Settings

PROVIDERS = {
    "1": ("openai", "OpenAI API", "https://api.openai.com/v1", "STATIC_OPENAI_API_KEY"),
    "2": ("anthropic", "Anthropic API", "https://api.anthropic.com/v1", "STATIC_ANTHROPIC_API_KEY"),
    "3": ("openai", "Custom OpenAI-compatible API", "", "STATIC_COMPAT_API_KEY"),
    "4": ("claude_code", "Installed Claude Code CLI", "", ""),
    "5": ("openai", "Existing local Ollama (NO DOWNLOAD)", "http://localhost:11434/v1", ""),
}


def secrets_path(data_dir):
    return Path(data_dir).expanduser().resolve() / "credentials.env"


def load_credentials(data_dir):
    path = secrets_path(data_dir)
    if path.exists():
        load_dotenv(path, override=False)


def _ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    value = input(prompt + suffix + ": ").strip()
    return value or default or ""


def _price(label):
    while True:
        try:
            value = float(_ask(label + " (USD per 1M tokens)", "0"))
            if not (0 <= value <= 10000):
                raise ValueError("Price must be between 0 and 10000")
            return value
        except ValueError:
            print("Enter a number, e.g. 1.50")


def _confirm(question):
    return _ask(question + " (type YES)", "") == "YES"


def configure(data_dir, existing=None):
    """Run explicitly from a terminal; cancellation never replaces prior settings."""
    data_dir = Path(data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    load_credentials(data_dir)
    print("\nStatic Code — AI provider setup")
    print("No AI model will be downloaded or installed.")
    print("1) OpenAI API")
    print("2) Anthropic API")
    print("3) Custom API (cloud HTTPS or local HTTP)")
    print("4) Existing Claude Code CLI login")
    print("5) Existing local Ollama model (no download)")
    print("0) Cancel setup")
    while True:
        choice = _ask("Provider", "1")
        if choice == "0":
            return False
        if choice in PROVIDERS:
            break
        print("Choose 0–5.")
    provider, name, base, key_env = PROVIDERS[choice]
    model_name = _ask("Exact model ID (check your provider's model list)")
    if not model_name:
        print("No model ID entered; configuration unchanged.")
        return False
    custom_local = False
    if choice == "3":
        base = _ask("Custom API base URL (https://host/v1 or http://localhost:8000/v1)")
        from urllib.parse import urlsplit
        from .config import LOCAL_HOSTS
        parsed = urlsplit(base)
        custom_local = parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS
        if parsed.scheme == "http" and not custom_local:
            print("Remote endpoints require HTTPS; local HTTP is allowed.")
            return False
    if choice == "5":
        base = _ask("Existing Ollama base URL", base)
        print("Make sure Ollama is running and the model is already installed.")
    if choice == "4":
        import shutil
        if not shutil.which("claude"):
            print("Claude Code CLI not found. Install and sign in separately first.")
            return False
        print("Static uses your existing Claude Code CLI login.")
    secret = None
    if choice == "3" and custom_local:
        if _ask("Does your local API need a key? (y/N)", "n").lower() not in ("y", "yes"):
            key_env = ""
    if key_env:
        secret = getpass.getpass("API key (hidden; Enter to reuse existing key): ").strip()
        if not secret and not os.getenv(key_env):
            print("API key is required. No settings changed.")
            return False
    local = choice == "5" or custom_local
    if not local:
        print("Cloud models can incur charges. Confirm your provider's actual prices.")
        input_price = _price("Input price")
        output_price = _price("Output price")
        if not _confirm("I have verified these prices and accept potential charges"):
            print("Configuration cancelled.")
            return False
    else:
        input_price = output_price = 0.0
    try:
        model = Model(
            id="terminal", name=name, provider=provider, model=model_name,
            base_url=base, key_env=key_env, local=local,
            pricing_confirmed=not local,
            input_per_million=input_price, output_per_million=output_price,
        )
        config = existing or Config(data_dir)
        settings = config.settings.model_copy(deep=True)
        settings.models = [model]
        Settings.model_validate(settings.model_dump())
    except (ValueError, TypeError) as exc:
        print("Invalid provider configuration:", exc)
        return False
    if secret:
        path = secrets_path(data_dir)
        path.touch(mode=0o600, exist_ok=True)
        if os.name != "nt":
            path.chmod(0o600)
        set_key(str(path), key_env, secret, quote_mode="always")
        os.environ[key_env] = secret
    config.save(settings)
    print("Provider saved. Static Code will not download any models.")
    return True
