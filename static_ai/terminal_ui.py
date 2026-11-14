"""Polished, low-overhead dark terminal presentation for Static Code.

Rich is installed by the [code] extra. Keep a plain-text fallback so
headless/remote uses can still start if the optional UI dependency is absent.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager

# The text palette is deliberately high-contrast on Raspberry Pi Connect.
BACKGROUND = "#0B1120"
PANEL = "#111D30"
USER_PANEL = "#17273D"
TEXT = "#E7F1FF"
MUTED = "#A4B7D0"
CYAN = "#67E8F9"
BLUE = "#60A5FA"
VIOLET = "#C4B5FD"
GREEN = "#6EE7B7"
AMBER = "#FCD34D"
RED = "#FDA4AF"


@contextmanager
def dark_terminal():
    """Set an xterm/VTE terminal palette just for this session, then restore it.

    OSC 10/11/12 also work in LXTerminal on typical Raspberry Pi OS installs.
    Never emit escape codes into pipes, captured output, or NO_COLOR terminals.
    Terminals without OSC support simply ignore these codes.
    """
    output = sys.stdout
    enabled = (
        hasattr(output, "isatty")
        and output.isatty()
        and os.environ.get("NO_COLOR") is None
        and os.environ.get("STATIC_TERMINAL_THEME", "dark").lower() == "dark"
        and os.environ.get("TERM") != "dumb"
    )
    if enabled:
        try:
            output.write(
                f"\x1b]10;{TEXT}\x07"
                f"\x1b]11;{BACKGROUND}\x07"
                f"\x1b]12;{CYAN}\x07"
            )
            output.flush()
        except (OSError, UnicodeError):
            enabled = False
    try:
        yield
    finally:
        if enabled:
            try:
                # Restore the user's terminal profile, not a hard-coded light scheme.
                output.write("\x1b]110\x07\x1b]111\x07\x1b]112\x07")
                output.flush()
            except (OSError, UnicodeError):
                pass


def prompt_style():
    """Color both the editor surface and the persistent status strip."""
    from prompt_toolkit.styles import Style

    return Style.from_dict(
        {
            "": f"fg:{TEXT} bg:{BACKGROUND}",
            "prompt": f"fg:{CYAN} bold bg:{BACKGROUND}",
            "bottom-toolbar": f"fg:{MUTED} bg:{PANEL}",
            "toolbar.brand": f"fg:{BACKGROUND} bg:{CYAN} bold",
            "toolbar.mode": f"fg:{VIOLET} bg:{PANEL} bold",
            "toolbar.active": f"fg:{GREEN} bg:{PANEL} bold",
            "toolbar.muted": f"fg:{MUTED} bg:{PANEL}",
            "toolbar.shortcut": f"fg:{CYAN} bg:{PANEL}",
            "completion-menu": f"fg:{TEXT} bg:{PANEL}",
            "completion-menu.completion": f"fg:{TEXT} bg:{PANEL}",
            "completion-menu.completion.current": f"fg:{BACKGROUND} bg:{CYAN} bold",
            "completion-menu.meta": f"fg:{MUTED} bg:{PANEL}",
            "scrollbar.background": f"bg:{PANEL}",
            "scrollbar.button": f"bg:{BLUE}",
        }
    )


def status_toolbar(project, mode, conversation_id, continuous=False, auto_approve=False):
    """A compact, styled status bar that remains legible in narrow Pi windows."""
    context = project.get("title", "")[:22] if project else mode.upper()
    flags = "● RUNNING" if continuous else "● READY"
    return [
        ("class:toolbar.brand", " ◈ STATIC "),
        ("class:toolbar.mode", f"  {context}  "),
        ("class:toolbar.active", f" {flags} "),
        ("class:toolbar.muted", f"  {str(conversation_id or '-')[:8]}  "),
        ("class:toolbar.shortcut", " /help  /projects  /extension "),
        ("class:toolbar.muted", "  AUTO " if auto_approve else ""),
    ]


def _console():
    from rich.console import Console

    return Console(highlight=False)


def show_banner():
    try:
        from rich.align import Align
        from rich.console import Group
        from rich.panel import Panel
        from rich.text import Text

        heading = Text("◈  S T A T I C   C O D E", style=f"bold {CYAN}")
        subheading = Text(
            "Your AI workspace  /  Build  ·  Research  ·  Automate",
            style=MUTED,
        )
        shortcuts = Text(" /help   /projects   /extension   /moneyfarm ", style=VIOLET)
        _console().print()
        _console().print(
            Panel(
                Group(
                    Align.center(heading),
                    Align.center(subheading),
                    Text(""),
                    Align.center(shortcuts),
                ),
                border_style=BLUE,
                style=f"on {PANEL}",
                padding=(1, 1),
                expand=True,
            )
        )
    except ImportError:
        print("\n◈ STATIC CODE  ·  /help  /projects  /extension  /moneyfarm\n")


def show_bubble(role, body):
    try:
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.text import Text

        ai = role.lower() in ("static", "assistant")
        name = "◈  STATIC  /  RESPONSE" if ai else "▸  YOU  /  MESSAGE"
        color = CYAN if ai else VIOLET
        content = Markdown(body or "*(No response text)*", code_theme="monokai") if ai else Text(
            body or "", style=TEXT
        )
        console = _console()
        console.print(
            Panel(
                content,
                title=Text(name, style=f"bold {color}"),
                title_align="left",
                border_style=color,
                padding=(1, 2) if console.size.width >= 70 else (0, 1),
                expand=True,
                style=f"on {PANEL if ai else USER_PANEL}",
            )
        )
    except ImportError:
        print(f"\n{role.upper()}:\n{body}\n")


def show_event(kind, value):
    """Subtle progress events: never interpret tool output as Rich markup."""
    icons = {
        "plan": ("◎", "PLAN", BLUE),
        "tool": ("◉", "TOOL", CYAN),
        "saved": ("✓", "DONE", GREEN),
        "error": ("!", "ERROR", RED),
        "warning": ("!", "NOTE", AMBER),
    }
    icon, label, color = icons.get(kind, ("·", "INFO", MUTED))
    try:
        from rich.text import Text

        line = Text()
        line.append(f" {icon} {label:<6} ", style=f"bold {color}")
        line.append(str(value)[:800], style=TEXT if kind == "error" else MUTED)
        _console().print(line, overflow="fold")
    except ImportError:
        print(f"  {label}: {str(value)[:800]}")


def show_plan(steps):
    """Display agent plans as an easily scanned checklist."""
    if not steps:
        return
    try:
        from rich.panel import Panel
        from rich.text import Text

        rendered = Text()
        markers = {"done": ("✓", GREEN), "active": ("◉", CYAN)}
        for step in steps[:12]:
            status = str(step.get("status", "pending"))
            icon, color = markers.get(status, ("○", MUTED))
            rendered.append(f" {icon}  ", style=color)
            rendered.append(str(step.get("title", ""))[:160], style=TEXT)
            rendered.append("\n")
        _console().print(
            Panel(
                rendered,
                title=Text("◎  PLAN", style=f"bold {BLUE}"),
                title_align="left",
                border_style=BLUE,
                style=f"on {PANEL}",
                padding=(0, 1),
            )
        )
    except ImportError:
        print("  PLAN: " + " → ".join(str(step.get("title", "")) for step in steps[:12]))


def show_run_summary(status, tools, spent):
    """A visible but compact end-of-run marker; never imply a sale happened."""
    color = GREEN if status == "completed" else RED
    try:
        from rich.text import Text

        line = Text()
        line.append(" ── ", style=MUTED)
        line.append(status.upper(), style=f"bold {color}")
        line.append(f"  ·  {tools} tool calls  ·  ~${spent:.4f} API estimate ", style=MUTED)
        _console().print(line)
    except ImportError:
        print(f"  Run {status} · {tools} tools · ~${spent:.4f} estimated API spend")


async def choose_chat(items):
    """Native up/down and Enter chooser. Escape/cancel falls back to last chat."""
    from prompt_toolkit.shortcuts import radiolist_dialog
    from prompt_toolkit.styles import Style

    if not items:
        return None
    values = [("__new__", "＋ New conversation")]
    values.extend((item["id"], f"{item['title'][:54]}  ·  {item['id'][:8]}") for item in items[:40])
    dialog = radiolist_dialog(
        title="◈ STATIC CODE  /  Saved chats",
        text="↑ / ↓ to select  ·  Enter to open  ·  Tab to buttons  ·  Esc to cancel",
        values=values,
        ok_text="Open",
        cancel_text="Cancel",
        style=Style.from_dict(
            {
                "dialog": f"bg:{BACKGROUND} fg:{TEXT}",
                "dialog frame.label": f"bg:{BACKGROUND} fg:{CYAN} bold",
                "dialog.body": f"bg:{PANEL} fg:{TEXT}",
                "radio": f"bg:{PANEL} fg:{TEXT}",
                "radio-selected": f"bg:{PANEL} fg:{CYAN} bold",
                "button": f"bg:{USER_PANEL} fg:{TEXT}",
                "button.focused": f"bg:{CYAN} fg:{BACKGROUND} bold",
            }
        ),
    )
    return await dialog.run_async()
