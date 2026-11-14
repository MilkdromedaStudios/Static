"""Regression coverage for Raspberry Pi dark terminal colors and Rich rendering."""

from io import StringIO
from pathlib import Path

from static_ai import terminal_ui


class FakeTTY(StringIO):
    def isatty(self):
        return True


def test_palette_changes_and_restores_terminal_colors(monkeypatch):
    fake = FakeTTY()
    monkeypatch.setattr(terminal_ui.sys, "stdout", fake)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("STATIC_TERMINAL_THEME", "dark")
    monkeypatch.setenv("TERM", "xterm-256color")
    with terminal_ui.dark_terminal():
        assert "\x1b]11;#0B1120\x07" in fake.getvalue()
        assert "\x1b]10;#E7F1FF\x07" in fake.getvalue()
        assert "\x1b]111\x07" not in fake.getvalue()
    assert fake.getvalue().endswith("\x1b]110\x07\x1b]111\x07\x1b]112\x07")


def test_no_escape_codes_for_pipes_no_color_or_system_theme(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setattr(terminal_ui.sys, "stdout", StringIO())
    with terminal_ui.dark_terminal():
        pass
    assert terminal_ui.sys.stdout.getvalue() == ""

    fake = FakeTTY()
    monkeypatch.setattr(terminal_ui.sys, "stdout", fake)
    monkeypatch.setenv("NO_COLOR", "1")
    with terminal_ui.dark_terminal():
        pass
    assert fake.getvalue() == ""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("STATIC_TERMINAL_THEME", "system")
    with terminal_ui.dark_terminal():
        pass
    assert fake.getvalue() == ""


def test_prompt_toolbar_and_style():
    toolbar = terminal_ui.status_toolbar(
        {"title": "Minecraft Studio"}, "economy", "abc123456789", True, True
    )
    joined = "".join(text for _, text in toolbar)
    assert "Minecraft Studio" in joined
    assert "RUNNING" in joined
    assert "AUTO" in joined
    assert "abc12345" in joined
    style = terminal_ui.prompt_style()
    assert style is not None


def test_rich_panels_show_content_without_crashing(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "120")
    terminal_ui.show_banner()
    terminal_ui.show_bubble("You", "Build a small Fabric pack")
    terminal_ui.show_bubble("Static", "## Ready\n\n- Step one\n- Step two")
    terminal_ui.show_plan([{"title": "Check licenses", "status": "done"}])
    terminal_ui.show_event("error", "[bold]Tool content should stay literal[/bold]")
    terminal_ui.show_run_summary("completed", 2, 0.0)
    result = capsys.readouterr().out
    for expected in ("STATIC", "Fabric", "Ready", "Check licenses", "Tool content", "COMPLETED"):
        assert expected in result


def test_installer_creates_dedicated_readable_lxterminal_profile():
    script = (Path(__file__).resolve().parent.parent / "install-linux.sh").read_text()
    assert "--profile=StaticCode" in script
    assert "--no-remote" in script
    assert "fontname=Monospace 13" in script
    assert "lxterminal-StaticCode.conf" in script
    assert "if [[ ! -f" in script
