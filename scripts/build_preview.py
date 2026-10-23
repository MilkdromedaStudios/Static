"""Export the same UI as a standalone GitHub Pages site.

The preview's workspace lives in the browser. Its chats give example replies,
or real ones from DigitBox AI once a visitor connects a DigitBox account (the
model API keys stay on DigitBox's server; none are ever part of this build).
"""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.0"
PAGES = ("index", "chat", "tasks", "create", "library", "skills", "connections", "settings")
# Where the preview connects for real answers. See docs/PREVIEW.md.
DIGITBOX_AI = {
    "api": "https://digitbox.pages.dev/api/ai",
    "connect": "https://digitbox.dev/ai/connect",
    "upgrade": "https://digitbox.dev/profile#digitbox-pro",
}


def build(output: Path, ai: dict | None = DIGITBOX_AI):
    output = output.resolve()
    if output == ROOT or output in ROOT.parents or output == ROOT / "static_ai":
        raise ValueError("Choose a separate output directory")
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    source = ROOT / "static_ai" / "static"
    for path in source.iterdir():
        if path.is_file() and path.name not in ("index.html", "mini.html"):
            shutil.copyfile(path, assets / path.name)
    runtime = f"mode: 'preview', version: '{VERSION}'"
    if ai:
        runtime += ", ai: Object.freeze(" + json.dumps(ai) + ")"
    (assets / "runtime.js").write_text(
        f"window.STATIC_RUNTIME = Object.freeze({{ {runtime} }});\n",
        encoding="utf-8",
    )
    html = (source / "index.html").read_text(encoding="utf-8")
    for page in PAGES:
        (output / (page + ".html")).write_text(html, encoding="utf-8")
    shutil.copyfile(source / "mini.html", output / "mini.html")
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
    parser.add_argument("--ai-api", default=DIGITBOX_AI["api"], help="DigitBox AI API root")
    parser.add_argument(
        "--ai-connect", default=DIGITBOX_AI["connect"], help="DigitBox AI connect page"
    )
    parser.add_argument("--no-ai", action="store_true", help="Example replies only; no DigitBox AI")
    args = parser.parse_args()
    ai = None if args.no_ai else {**DIGITBOX_AI, "api": args.ai_api, "connect": args.ai_connect}
    print(f"Static preview ready: {build(args.output, ai)}")
