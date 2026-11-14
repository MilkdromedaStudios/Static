"""Optional dark terminal presentation for Static Code."""

from __future__ import annotations


def show_banner():
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        Console().print(
            Panel(
                Text(
                    "S T A T I C   C O D E\nGoals  •  Projects  •  Tools  •  Saved chats",
                    justify="center",
                    style="bold bright_cyan",
                ),
                border_style="bright_blue",
                style="on #101827",
            )
        )
    except ImportError:
        print("STATIC CODE  •  Projects  •  /help  •  saved chats")


def show_bubble(role, body):
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.text import Text

        palette = "bright_cyan" if role.lower() == "static" else "magenta"
        title = "◈ STATIC" if role.lower() == "static" else "YOU"
        content = Markdown(body or "(empty)") if role.lower() == "static" else Text(body)
        Console().print(
            Panel(
                content,
                title=title,
                title_align="left",
                border_style=palette,
                padding=(1, 2),
                expand=True,
                style="on #101827",
            )
        )
    except ImportError:
        print(f"\n{role}:\n{body}\n")


def show_event(kind, value):
    try:
        from rich.console import Console

        icon = {"plan": "◎", "tool": "⚙", "saved": "✓", "error": "!"}.get(kind, "·")
        color = "red" if kind == "error" else "bright_blue"
        Console().print(f"[{color}]{icon}[/] {str(value)[:500]}")
    except ImportError:
        print(f"  {kind}: {value}")


async def choose_chat(items):
    """Native up/down and Enter chooser. Escape/cancel falls back to last chat."""
    from prompt_toolkit.shortcuts import radiolist_dialog
    from prompt_toolkit.styles import Style

    if not items:
        return None
    values = [("__new__", "＋ New conversation")]
    values.extend((item["id"], f"{item['title'][:54]}  ·  {item['id'][:8]}") for item in items[:40])
    dialog = radiolist_dialog(
        title="STATIC · Saved Chats",
        text="↑ / ↓ to choose  ·  Enter to open  ·  Tab to buttons  ·  Esc to cancel",
        values=values,
        ok_text="Open",
        cancel_text="Use last",
        style=Style.from_dict(
            {
                "dialog": "bg:#101827 #e3edff",
                "dialog frame.label": "bg:#101827 #6edaff bold",
                "dialog.body": "bg:#151d31 #e3edff",
                "button": "bg:#254066 #e3edff",
                "button.focused": "bg:#45b4f8 #061124 bold",
            }
        ),
    )
    return await dialog.run_async()
