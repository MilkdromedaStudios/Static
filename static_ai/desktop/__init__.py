"""Optional Windows desktop shell. The core server does not require Qt."""


def main():
    from .gui import main as desktop_main

    return desktop_main()
