import argparse
import os


def main():
    from dotenv import load_dotenv

    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Buns AI workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default=os.getenv("BUNS_DATA_DIR", "data"))
    args = parser.parse_args()
    if (
        args.host not in ("127.0.0.1", "localhost", "::1")
        and len(os.getenv("BUNS_AUTH_TOKEN", "")) < 24
    ):
        parser.error(
            "For network access, set BUNS_AUTH_TOKEN to at least 24 random characters and BUNS_ALLOWED_HOSTS to your hostname"
        )
    import uvicorn

    from .app import create_app

    print(f"Buns is starting at http://{args.host}:{args.port}")
    uvicorn.run(create_app(args.data_dir), host=args.host, port=args.port, workers=1)
