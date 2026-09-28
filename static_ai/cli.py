import argparse

from .bootstrap import ensure_local_model
from .config import env


def main():
    from dotenv import load_dotenv

    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Static AI workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default=env("DATA_DIR", "data"))
    parser.add_argument(
        "--skip-local-setup", action="store_true", help="Do not start or install Ollama"
    )
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1") and len(env("AUTH_TOKEN")) < 24:
        parser.error(
            "For network access, set STATIC_AUTH_TOKEN to at least 24 random characters and STATIC_ALLOWED_HOSTS to your hostname"
        )
    import uvicorn

    from .app import create_app

    app = create_app(args.data_dir)
    if not args.skip_local_setup:
        ensure_local_model(app.state.config)
    print(f"Static is starting at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, workers=1)
