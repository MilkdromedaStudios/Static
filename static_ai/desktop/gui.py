"""Static's Windows shell, tray lifecycle, native setup and embedded workspace."""

import argparse
import json
import logging
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QSystemTrayIcon,
    QToolBar,
)

from .. import __version__
from ..bootstrap import ensure_local_model
from ..config import Config
from .credentials import CredentialStore
from .runtime import LocalServer
from .setup import KeysDialog, SetupDialog
from .state import (
    RELEASES_URL,
    default_data_dir,
    instance_name,
    read_preferences,
    save_preferences,
    set_login_start,
)

ASSETS = Path(__file__).resolve().parents[1] / "static"


class AuthInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, base_url, token, parent=None):
        super().__init__(parent)
        self.origin, self.token = QUrl(base_url), token.encode()

    def interceptRequest(self, request):
        url = request.requestUrl()
        if (
            url.scheme() == self.origin.scheme()
            and url.host() == self.origin.host()
            and url.port() == self.origin.port()
        ):
            request.setHttpHeader(b"Authorization", b"Bearer " + self.token)
        elif url.scheme() not in ("data", "blob", "about"):
            request.block(True)


class WorkspacePage(QWebEnginePage):
    def __init__(self, profile, controller, mini, parent):
        super().__init__(profile, parent)
        self.controller, self.mini = controller, mini
        self.newWindowRequested.connect(lambda request: controller.open_url(request.requestedUrl()))

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if url.scheme() == "about":
            return True
        if not self.controller.internal(url):
            if (
                is_main_frame
                and navigation_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked
            ):
                self.controller.open_url(url)
            return False
        if is_main_frame:
            if self.mini and url.path() != "/mini.html":
                self.controller.show_workspace(url)
                self.controller.mini.hide()
                return False
            if not self.mini and url.path() == "/mini.html":
                self.controller.show_mini(url)
                return False
        return True


class WorkspaceWindow(QMainWindow):
    def __init__(self, controller, mini=False):
        super().__init__()
        self.controller, self.is_mini = controller, mini
        self.setWindowTitle(("Quick chat" if mini else "Static") + f" · {__version__}")
        self.setWindowIcon(controller.icon)
        self.view = QWebEngineView()
        self.view.setPage(WorkspacePage(controller.profile, controller, mini, self.view))
        self.setCentralWidget(self.view)
        if mini:
            self.setMinimumSize(340, 440)
            self.resize(440, 640)
            self.setWindowFlag(
                Qt.WindowType.WindowStaysOnTopHint, controller.preferences.mini_on_top
            )
        else:
            self.setMinimumSize(800, 600)
            self.resize(controller.preferences.window_width, controller.preferences.window_height)
            menu = self.menuBar().addMenu("Static")
            for label, action in (
                ("Quick chat", controller.show_mini),
                ("AI setup…", controller.setup),
                ("API keys…", controller.keys),
                ("Open data folder", controller.open_data),
                ("Downloads and updates", controller.releases),
                ("About Static", controller.about),
                ("Quit", controller.quit),
            ):
                menu.addAction(label, action)
            options = self.menuBar().addMenu("Options")
            for label, field in (
                ("Minimize and close to tray", "minimize_to_tray"),
                ("Keep quick chat on top", "mini_on_top"),
                ("Start at Windows login", "start_at_login"),
            ):
                choice = QAction(label, self)
                choice.setCheckable(True)
                choice.setChecked(getattr(controller.preferences, field))
                choice.triggered.connect(
                    lambda checked, name=field, a=choice: controller.option(name, checked, a)
                )
                if field == "start_at_login" and not getattr(sys, "frozen", False):
                    choice.setEnabled(False)
                options.addAction(choice)
            toolbar = QToolBar("Quick actions")
            toolbar.setMovable(False)
            toolbar.addAction("Quick chat", controller.show_mini)
            toolbar.addAction("AI setup", controller.setup)
            toolbar.addAction("API keys", controller.keys)
            toolbar.addAction("Hide to tray", controller.hide_workspace)
            self.addToolBar(toolbar)

    def changeEvent(self, event):
        if (
            event.type() == event.Type.WindowStateChange
            and self.isMinimized()
            and not self.is_mini
            and self.controller.preferences.minimize_to_tray
            and self.controller.tray_available
        ):
            QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.is_mini:
            self.hide()
            event.ignore()
        elif self.controller.preferences.minimize_to_tray and self.controller.tray_available:
            self.hide()
            event.ignore()
        elif self.controller.quit():
            event.accept()
        else:
            event.ignore()


class LocalSetupWorker(QThread):
    question = Signal(str, object)
    failed = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def ask(self, question):
        result = {"answer": False, "ready": threading.Event()}
        self.question.emit(question, result)
        result["ready"].wait()
        return result["answer"]

    def run(self):
        try:
            ensure_local_model(self.config, ask=self.ask)
        except Exception:
            logging.exception("Local model setup did not finish")
            self.failed.emit(
                "Local model setup did not finish. You can retry AI setup or use an API key. Details are in desktop.log."
            )


class Controller(QObject):
    def __init__(self, qt, server, credentials, preferences):
        super().__init__()
        self.qt, self.server, self.credentials, self.preferences = (
            qt,
            server,
            credentials,
            preferences,
        )
        self.root, self.config = server.app.state.config.root, server.app.state.config
        self.worker, self.progress = None, None
        self.icon = QIcon(str(ASSETS / "static.svg"))
        self.profile = QWebEngineProfile("Static", self)
        self.profile.setPersistentStoragePath(str(self.root / "webview"))
        self.profile.setCachePath(str(self.root / "webview-cache"))
        self.interceptor = AuthInterceptor(server.url, server.token, self.profile)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        self.profile.downloadRequested.connect(self.download)
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip("Static · click for quick chat")
        self.window = WorkspaceWindow(self)
        self.mini = WorkspaceWindow(self, mini=True)
        self.window.view.setUrl(QUrl(server.url + "/index.html"))
        self.mini.view.setUrl(QUrl(server.url + "/mini.html"))
        self.tray_menu = QMenu()
        for label, action in (
            ("Quick chat", self.show_mini),
            ("Open workspace", self.show_workspace),
            ("AI setup…", self.setup),
            ("API keys…", self.keys),
            ("Downloads and updates", self.releases),
        ):
            self.tray_menu.addAction(label, action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("Quit Static", self.quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.tray_clicked)
        if self.tray_available:
            self.tray.show()
        qt.aboutToQuit.connect(self.shutdown)

    def internal(self, url):
        origin = QUrl(self.server.url)
        return (url.scheme(), url.host(), url.port()) == (
            origin.scheme(),
            origin.host(),
            origin.port(),
        )

    def open_url(self, url):
        if self.internal(url):
            self.show_mini(url) if url.path() == "/mini.html" else self.show_workspace(url)
        elif url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)

    def show_workspace(self, url=None):
        if isinstance(url, QUrl) and self.internal(url):
            self.window.view.setUrl(url)
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def show_mini(self, url=None):
        if isinstance(url, QUrl) and self.internal(url):
            self.mini.view.setUrl(url)
        rect = self.qt.primaryScreen().availableGeometry()
        self.mini.move(
            rect.right() - self.mini.width() - 16, rect.bottom() - self.mini.height() - 16
        )
        self.mini.showNormal()
        self.mini.raise_()
        self.mini.activateWindow()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.mini.hide() if self.mini.isVisible() else self.show_mini()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_workspace()

    def hide_workspace(self):
        self.window.hide() if self.tray_available else self.window.showMinimized()

    def can_configure(self):
        if self.server.busy() or (self.worker and self.worker.isRunning()):
            QMessageBox.information(
                self.window,
                "Finish the current task",
                "Finish or stop active tasks and local model setup before changing AI connections.",
            )
            return False
        return True

    def setup(self):
        if not self.can_configure():
            return
        dialog = SetupDialog(self.config, self.credentials, self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            if dialog.secret:
                self.credentials.save(dialog.selected_model.key_env, dialog.secret)
            settings = self.config.settings.model_copy(deep=True)
            settings.models = [dialog.selected_model]
            self.config.save(settings)
            self.preferences.onboarded = True
            save_preferences(self.root, self.preferences)
            self.window.view.reload()
            self.mini.view.reload()
            self.prepare_local()
        except Exception:
            logging.exception("Could not save AI configuration")
            QMessageBox.warning(
                self.window,
                "Could not save AI setup",
                "The connection could not be saved. Check desktop.log in your data folder.",
            )

    def keys(self):
        if (
            self.can_configure()
            and KeysDialog(self.config, self.credentials, self.window).exec()
            == QDialog.DialogCode.Accepted
        ):
            self.window.view.reload()
            self.mini.view.reload()

    def prepare_local(self):
        if not any(m.local and ":11434" in m.base_url for m in self.config.settings.models):
            return
        self.worker = LocalSetupWorker(self.config)
        self.worker.question.connect(self.answer)
        self.worker.failed.connect(
            lambda text: QMessageBox.warning(self.window, "Local model setup", text)
        )
        self.progress = QProgressDialog(
            "Preparing your local AI. Installers may take several minutes. Static asks before downloads.",
            "",
            0,
            0,
            self.window,
        )
        self.progress.setWindowTitle("Local AI · Static")
        self.progress.setCancelButton(None)
        self.progress.setMinimumDuration(0)
        self.worker.finished.connect(self.finish_local)
        self.worker.start()

    def answer(self, question, result):
        result["answer"] = (
            QMessageBox.question(
                self.window,
                "Local AI · Static",
                question,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )
        result["ready"].set()

    def finish_local(self):
        if self.progress:
            self.progress.close()
        self.window.view.reload()
        self.mini.view.reload()

    def option(self, name, checked, action):
        try:
            if name == "start_at_login":
                set_login_start(checked)
            setattr(self.preferences, name, checked)
            if name == "mini_on_top":
                visible = self.mini.isVisible()
                self.mini.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
                if visible:
                    self.show_mini()
            save_preferences(self.root, self.preferences)
        except Exception as exc:
            action.setChecked(not checked)
            QMessageBox.warning(self.window, "Could not change this option", str(exc))

    def download(self, request):
        name = Path(request.downloadFileName()).name
        target, _ = QFileDialog.getSaveFileName(
            self.window, "Save from Static", str(Path.home() / "Downloads" / name)
        )
        if target:
            request.setDownloadDirectory(str(Path(target).parent))
            request.setDownloadFileName(Path(target).name)
            request.accept()
        else:
            request.cancel()

    def open_data(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root)))

    def releases(self):
        QDesktopServices.openUrl(QUrl(RELEASES_URL))

    def about(self):
        QMessageBox.about(
            self.window,
            "About Static",
            f"Static {__version__}\nMilkdromeda Studios\n\nYour personal AI workspace.\nPython and the desktop runtime are included.\nThird-party notices and licenses are in the installation folder.\n\nClose/minimize keeps tasks running in the tray. Quit stops the local service.",
        )

    def quit(self, force=False):
        if self.worker and self.worker.isRunning():
            if not force:
                QMessageBox.information(
                    self.window,
                    "Local setup is running",
                    "Finish the current installer or model download before quitting.",
                )
            return False
        if self.server.busy() and not force:
            if (
                QMessageBox.question(
                    self.window,
                    "Quit Static?",
                    "An AI task is active. Quit stops it; completed files and chats stay saved.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return False
        self.qt.quit()
        return True

    def shutdown(self):
        self.tray.hide()
        if not self.window.isMinimized():
            self.preferences.window_width = min(4000, max(800, self.window.width()))
            self.preferences.window_height = min(2400, max(600, self.window.height()))
        save_preferences(self.root, self.preferences)
        self.server.stop()
        # Pages must be destroyed before their shared WebEngine profile.
        self.window.view.setPage(QWebEnginePage(self.window.view))
        self.mini.view.setPage(QWebEnginePage(self.mini.view))
        self.window.deleteLater()
        self.mini.deleteLater()


def contact_instance(name, message):
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(1000):
        return None
    socket.write(message.encode())
    socket.flush()
    if not socket.waitForReadyRead(3000):
        return "busy"
    answer = bytes(socket.readAll()).decode()
    socket.disconnectFromServer()
    return answer


def smoke_test(controller, report):
    """Exercise the packaged UI/credentials/server, using only a fixture provider."""
    checks = {}
    attempts = [0]
    controller.show_workspace()
    dialog = SetupDialog(controller.config, controller.credentials, controller.window)
    dialog.mode.setCurrentIndex(0)
    dialog.name.setText("Test API")
    dialog.endpoint.setText("https://api.example.com/v1")
    dialog.model.setText("tool-model")
    dialog.key.setText("desktop-fixture-key")
    dialog.confirm.setChecked(True)
    dialog.accept()
    checks["setup_api_choice"] = (
        dialog.result() == QDialog.DialogCode.Accepted and not dialog.selected_model.local
    )
    dialog.mode.setCurrentIndex(1)
    dialog.accept()
    checks["setup_local_choice"] = dialog.selected_model.local
    controller.credentials.save("STATIC_SMOKE_KEY", "desktop-fixture-key")
    checks["credential_roundtrip"] = (
        controller.credentials.get("STATIC_SMOKE_KEY") == "desktop-fixture-key"
    )
    controller.credentials.delete("STATIC_SMOKE_KEY")
    checks["credential_removal"] = controller.credentials.get("STATIC_SMOKE_KEY") is None
    checks["tray_menu"] = len(controller.tray_menu.actions()) >= 7
    checks["tray_available"] = controller.tray_available
    from urllib.error import HTTPError
    from urllib.request import ProxyHandler, build_opener

    try:
        build_opener(ProxyHandler({})).open(controller.server.url + "/api/settings")
        checks["unauthenticated_blocked"] = False
    except HTTPError as exc:
        checks["unauthenticated_blocked"] = exc.code == 401
    timer = QTimer(controller)
    timer.setInterval(500)

    def finish(success):
        timer.stop()
        controller.credentials.delete_all()
        report.parent.mkdir(parents=True, exist_ok=True)
        controller.window.grab().save(str(report.parent / "desktop-workspace.png"))
        controller.mini.grab().save(str(report.parent / "desktop-quick-chat.png"))
        report.write_text(
            json.dumps({"ok": success, "version": __version__, "checks": checks}, indent=2),
            encoding="utf-8",
        )
        controller.qt.exit(0 if success else 1)

    def received(value):
        if not value:
            return
        if not checks.get("main_loaded") and value.get("main"):
            checks["main_loaded"] = True
            controller.hide_workspace()
            checks["hide_restore"] = (
                not controller.window.isVisible()
                if controller.tray_available
                else controller.window.isMinimized()
            )
            controller.show_workspace()
            controller.show_mini()
        if value.get("mini") and not checks.get("sent"):
            checks["sent"] = True
            controller.mini.view.page().runJavaScript(
                "document.querySelector('#mini-prompt').value = 'Hello from the packaged app'; document.querySelector('#mini-compose').requestSubmit();"
            )
        if value.get("reply"):
            checks["mini_authenticated_chat"] = True
            finish(
                all(
                    checks.get(k)
                    for k in (
                        "setup_api_choice",
                        "setup_local_choice",
                        "credential_roundtrip",
                        "credential_removal",
                        "tray_menu",
                        "unauthenticated_blocked",
                        "main_loaded",
                        "hide_restore",
                        "mini_authenticated_chat",
                    )
                )
            )

    def tick():
        attempts[0] += 1
        if attempts[0] > 100:
            finish(False)
            return
        if checks.get("main_loaded"):
            controller.mini.view.page().runJavaScript(
                "({mini: Boolean(document.querySelector('#mini-prompt')), reply: Boolean(document.querySelector('.mini-message.assistant'))})",
                0,
                received,
            )
        else:
            controller.window.view.page().runJavaScript(
                "({main: Boolean(document.querySelector('#main h1'))})", 0, received
            )

    timer.timeout.connect(tick)
    timer.start()


def main():
    parser = argparse.ArgumentParser(description="Static Windows desktop workspace")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--mini", action="store_true")
    parser.add_argument(
        "--quit", action="store_true", help="Ask an existing instance to exit (installer use)"
    )
    parser.add_argument(
        "--cleanup-credentials",
        action="store_true",
        help="Remove Static's saved Windows keys (uninstaller use)",
    )
    parser.add_argument(
        "--smoke-test", type=Path, help="Test an empty isolated workspace without real AI calls"
    )
    args = parser.parse_args()
    root = (args.data_dir or default_data_dir()).resolve()
    if args.smoke_test and (
        not args.data_dir or (root / "static.db").exists() or (root / "settings.json").exists()
    ):
        parser.error("Smoke tests require --data-dir pointing to a new isolated workspace.")
    root.mkdir(parents=True, exist_ok=True)
    logfile = (root / "desktop.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = logfile
    if sys.stderr is None:
        sys.stderr = logfile
    logging.basicConfig(filename=root / "desktop.log", level=logging.WARNING)
    credentials = CredentialStore(root)
    if args.cleanup_credentials:
        credentials.delete_all()
        set_login_start(False)
        return 0
    qt = QApplication([sys.argv[0]])
    qt.setApplicationName("Static")
    qt.setOrganizationName("Milkdromeda Studios")
    qt.setApplicationVersion(__version__)
    qt.setQuitOnLastWindowClosed(False)
    name = instance_name(root)
    command = "quit" if args.quit else "mini" if args.mini else "show"
    existing = contact_instance(name, command)
    if existing is not None:
        if args.quit and existing == "ok":
            probe = QLockFile(str(root / "desktop.lock"))
            probe.setStaleLockTime(0)
            for _ in range(150):
                if probe.tryLock(0):
                    probe.unlock()
                    return 0
                QThread.msleep(100)
            return 2
        return 0 if existing == "ok" else 2
    if args.quit:
        return 0
    lock = QLockFile(str(root / "desktop.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.warning(
            None, "Static is already starting", "Wait a moment, then open Static again."
        )
        return 2
    from dotenv import load_dotenv

    load_dotenv(root / ".env")
    credentials.load()
    config = Config(root)
    preferences = read_preferences(root)
    if not preferences.onboarded and not args.smoke_test:
        dialog = SetupDialog(config, credentials)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.secret:
                credentials.save(dialog.selected_model.key_env, dialog.secret)
            settings = config.settings.model_copy(deep=True)
            settings.models = [dialog.selected_model]
            config.save(settings)
            preferences.onboarded = True
    transport = None
    if args.smoke_test:
        import httpx

        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "Packaged chat works."}}
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                },
            )
        )
    server = LocalServer(root, transport, preferences.server_port)
    server.start()
    preferences.server_port = QUrl(server.url).port()
    save_preferences(root, preferences)
    controller = Controller(qt, server, credentials, preferences)
    ipc = QLocalServer()
    ipc.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(name)
    if not ipc.listen(name):
        controller.shutdown()
        raise RuntimeError("Could not create Static's single-instance channel.")

    def new_connection():
        connection = ipc.nextPendingConnection()

        def receive():
            message = bytes(connection.readAll()).decode()
            accepted = True
            if message == "quit":
                accepted = controller.quit(force=True)
            elif message == "mini":
                controller.show_mini()
            elif message == "show":
                controller.show_workspace()
            else:
                accepted = False
            connection.write(b"ok" if accepted else b"busy")
            connection.flush()
            connection.disconnectFromServer()
            connection.deleteLater()

        connection.readyRead.connect(receive)
        if connection.bytesAvailable():
            receive()

    ipc.newConnection.connect(new_connection)
    if args.smoke_test:
        QTimer.singleShot(0, lambda: smoke_test(controller, args.smoke_test))
    else:
        if args.mini:
            controller.show_mini()
        elif not args.minimized or not controller.tray_available:
            controller.show_workspace()
        if preferences.onboarded:
            QTimer.singleShot(250, controller.prepare_local)
    result = qt.exec()
    ipc.close()
    lock.unlock()
    return result
