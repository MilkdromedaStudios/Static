"""Windowed PyInstaller entry point; show startup errors without a console."""

import ctypes
import logging
import sys

from static_ai.desktop import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception("Static could not start")
        if sys.platform == "win32" and "--smoke-test" not in sys.argv:
            ctypes.windll.user32.MessageBoxW(
                None,
                "Static could not start. Check desktop.log in %LOCALAPPDATA%\\StaticAI. Your saved files and chats remain in that folder.",
                "Static startup",
                0x10,
            )
        raise SystemExit(1)
