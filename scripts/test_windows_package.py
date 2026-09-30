"""Windows release gate: frozen UI, silent install, keys, and data-preserving uninstall."""

import json
import shutil
import subprocess
import sys
import tempfile
import winreg
from pathlib import Path

from static_ai.desktop.credentials import CredentialStore
from static_ai.desktop.state import default_data_dir

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "test-results/windows"


def smoke(executable, data, name):
    report = RESULTS / name / "report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(executable), "--data-dir", str(data), "--smoke-test", str(report)],
        timeout=130,
        check=False,
    )
    if (
        result.returncode
        or not report.exists()
        or not json.loads(report.read_text(encoding="utf-8"))["ok"]
    ):
        raise RuntimeError(
            f"Packaged app smoke failed: {name}. See {report} and {data / 'desktop.log'}"
        )


def main():
    if sys.platform != "win32":
        raise SystemExit("Run this release gate on Windows.")
    RESULTS.mkdir(parents=True, exist_ok=True)
    installers = list((ROOT / "release").glob("*-Setup.exe"))
    if len(installers) != 1:
        raise RuntimeError("Expected one freshly built installer")
    root = default_data_dir()
    if root.exists():
        raise RuntimeError(
            "This test needs a clean CI account without an existing Static workspace."
        )
    with tempfile.TemporaryDirectory(prefix="static-release-") as temporary:
        stage = Path(temporary)
        smoke(ROOT / "dist/Static/Static.exe", stage / "portable-data", "portable")
        installed = stage / "installed app"
        subprocess.run(
            [
                str(installers[0]),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                f"/DIR={installed}",
                f"/LOG={RESULTS / 'install.log'}",
            ],
            check=True,
            timeout=180,
        )
        smoke(installed / "Static.exe", stage / "installed-data", "installed")
        root.mkdir(parents=True)
        proof = root / "keep-my-work.txt"
        proof.write_text("Uninstall should preserve this by default.", encoding="utf-8")
        credentials = CredentialStore(root)
        credentials.save("STATIC_UNINSTALL_TEST_KEY", "ci-not-a-real-api-key")
        run_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, run_path) as key:
            winreg.SetValueEx(
                key, "StaticAI", 0, winreg.REG_SZ, f'"{installed / "Static.exe"}" --minimized'
            )
        try:
            subprocess.run(
                [
                    str(installed / "unins000.exe"),
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                    f"/LOG={RESULTS / 'uninstall.log'}",
                ],
                check=True,
                timeout=180,
            )
            assert not (installed / "Static.exe").exists(), "Uninstall left the app executable"
            assert proof.is_file(), "Silent uninstall deleted user work"
            assert credentials.get("STATIC_UNINSTALL_TEST_KEY") is None, (
                "Uninstall left a saved API key"
            )
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_path) as key:
                try:
                    winreg.QueryValueEx(key, "StaticAI")
                except FileNotFoundError:
                    pass
                else:
                    raise AssertionError("Uninstall left start-at-login enabled")
            (RESULTS / "installer-report.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "install": True,
                        "uninstall": True,
                        "data_kept_by_default": True,
                        "credentials_removed": True,
                        "login_start_removed": True,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        finally:
            credentials.delete_all()
            shutil.rmtree(root)
    print("Windows app, installer, and uninstall checks passed.")


if __name__ == "__main__":
    main()
