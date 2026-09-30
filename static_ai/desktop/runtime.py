"""An authenticated loopback server owned by the desktop app."""

import os
import secrets
import socket
import threading
import time

import uvicorn

from ..app import create_app


class LocalServer:
    def __init__(self, root, transport=None, port=0):
        self.token = secrets.token_urlsafe(48)
        os.environ["STATIC_AUTH_TOKEN"] = self.token
        os.environ["STATIC_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
        self.app = create_app(root, transport)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind(("127.0.0.1", port))
        except OSError:
            self.socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.server = uvicorn.Server(
            uvicorn.Config(self.app, host="127.0.0.1", log_level="warning", log_config=None)
        )
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True
        )

    def start(self):
        self.thread.start()
        deadline = time.monotonic() + 15
        while not self.server.started and self.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not self.server.started:
            self.stop()
            raise RuntimeError(
                "Static's local service could not start. See desktop.log in your data folder."
            )

    def stop(self):
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout=8)
        self.socket.close()

    def busy(self):
        return bool(
            self.app.state.store.one(
                "SELECT id FROM runs WHERE status IN ('queued','running','awaiting_approval')"
            )
        )
