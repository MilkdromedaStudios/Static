"""Regression tests: terminal setup never downloads models and saves provider configuration."""
import os
from unittest.mock import patch

from static_ai.config import Config
from static_ai.terminal_setup import configure


def test_first_run_cloud_model_no_download(tmp_path):
    answers = iter(["1", "gpt-test", "0.50", "2.00", "YES"])
    with patch("builtins.input", side_effect=lambda *_: next(answers)), \
         patch("getpass.getpass", return_value="example-key"), \
         patch.dict(os.environ, {}, clear=True):
        assert configure(tmp_path)
        cfg = Config(tmp_path)
        assert cfg.settings.models[0].model == "gpt-test"
        assert cfg.settings.models[0].local is False
        assert "example-key" not in cfg.path.read_text()
        assert "example-key" in (tmp_path / "credentials.env").read_text()


def test_cancel_keeps_previous_settings(tmp_path):
    with patch("builtins.input", return_value="0"):
        assert not configure(tmp_path)
    assert not (tmp_path / "settings.json").exists()


def test_existing_ollama_requires_no_download(tmp_path):
    answers = iter(["5", "existing-model", ""])
    with patch("builtins.input", side_effect=lambda *_: next(answers)):
        assert configure(tmp_path)
    assert Config(tmp_path).settings.models[0].local is True

def test_custom_local_api_without_key(tmp_path):
    answers = iter(["3", "my-local-model", "http://localhost:8000/v1", "n"])
    with patch("builtins.input", side_effect=lambda *_: next(answers)):
        assert configure(tmp_path)
    model = Config(tmp_path).settings.models[0]
    assert model.base_url == "http://localhost:8000/v1"
    assert model.key_env == ""
    assert model.local is True


def test_custom_remote_http_rejected(tmp_path):
    answers = iter(["3", "my-model", "http://example.com/v1"])
    with patch("builtins.input", side_effect=lambda *_: next(answers)):
        assert not configure(tmp_path)
    assert not (tmp_path / "settings.json").exists()

def test_custom_https_without_key(tmp_path):
    answers = iter(["3", "remote-model", "https://models.example.org/api/v1", "n", "0", "0", "YES"])
    with patch("builtins.input", side_effect=lambda *_: next(answers)):
        assert configure(tmp_path)
    model = Config(tmp_path).settings.models[0]
    assert model.base_url == "https://models.example.org/api/v1"
    assert model.key_env == ""
    assert model.local is False
