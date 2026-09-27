"""Export the same UI as a standalone, explicitly simulated GitHub Pages site."""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("index", "chat", "tasks", "create", "library", "skills", "connections", "settings")


def build(output: Path):
    output = output.resolve()
    if output == ROOT or output in ROOT.parents or output == ROOT / "static_ai":
        raise ValueError("Choose a separate output directory")
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    source = ROOT / "static_ai" / "static"
    for path in source.iterdir():
        if path.is_file() and path.name != "index.html":
            shutil.copyfile(path, assets / path.name)
    (assets / "runtime.js").write_text(
        "window.STATIC_RUNTIME = Object.freeze({ mode: 'preview', version: '0.2.0' });\n",
        encoding="utf-8",
    )
    html = (source / "index.html").read_text(encoding="utf-8")
    for page in PAGES:
        (output / (page + ".html")).write_text(html, encoding="utf-8")
    (output / ".nojekyll").touch()
    # A helpful 404 with relative links; deep links always have real HTML entry points.
    (output / "404.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        "<title>Page not found · Static</title><body><h1>A fresh start?</h1>"
        '<p>This page does not exist. <a href="./index.html">Open Static</a>.</p></body></html>',
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    print(f"Static preview ready: {build(args.output)}")
