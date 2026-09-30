"""Build a bundled Windows app, per-user installer, ZIP, notices and checksums."""

import hashlib
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_version():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Windows releases need a three-part numeric version.")
    from static_ai import __version__

    if version != __version__:
        raise ValueError("pyproject.toml and static_ai.__version__ must match")
    return version


def make_icon(output):
    from PIL import Image
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(str(ROOT / "static_ai/static/static.svg")).render(painter, QRectF(0, 0, 256, 256))
    painter.end()
    output.parent.mkdir(parents=True, exist_ok=True)
    png = output.with_suffix(".png")
    if not image.save(str(png)):
        raise RuntimeError("Could not generate Static's Windows icon")
    Image.open(png).save(
        output, format="ICO", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)]
    )


def copy_licenses(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for distribution in importlib.metadata.distributions():
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", distribution.metadata["Name"])
        for file in distribution.files or []:
            if re.search(r"(^|/)(licenses?|copying|notice)([^/]*)(/|$)", str(file), re.I):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    relative = Path(*file.parts[1:]) if len(file.parts) > 1 else Path(file.name)
                    target = destination / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)


def main():
    if sys.platform != "win32":
        raise SystemExit("Build Windows binaries on Windows (or use the GitHub release workflow).")
    os.chdir(ROOT)
    version = project_version()
    branding = ROOT / "build/branding"
    icon = branding / "static.ico"
    make_icon(icon)
    numbers = tuple(int(n) for n in version.split(".")) + (0,)
    info = branding / "version.txt"
    info.write_text(
        f"VSVersionInfo(ffi=FixedFileInfo(filevers={numbers!r}, prodvers={numbers!r}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('CompanyName', 'Milkdromeda Studios'), StringStruct('FileDescription', 'Static AI workspace'), StringStruct('FileVersion', '{version}'), StringStruct('InternalName', 'Static'), StringStruct('OriginalFilename', 'Static.exe'), StringStruct('ProductName', 'Static'), StringStruct('ProductVersion', '{version}')])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])",
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--name",
            "Static",
            "--icon",
            str(icon),
            "--version-file",
            str(info),
            "--add-data",
            f"{ROOT / 'static_ai/static'};static_ai/static",
            "--hidden-import",
            "PySide6.QtSvg",
            "--hidden-import",
            "uvicorn.logging",
            "--hidden-import",
            "uvicorn.loops.asyncio",
            "--hidden-import",
            "uvicorn.protocols.http.h11_impl",
            "--hidden-import",
            "uvicorn.lifespan.on",
            "scripts/windows_entry.py",
        ],
        check=True,
    )
    bundled = ROOT / "dist/Static"
    shutil.copyfile(ROOT / "LICENSE", bundled / "LICENSE.txt")
    shutil.copyfile(ROOT / "packaging/THIRD_PARTY_NOTICES.md", bundled / "THIRD_PARTY_NOTICES.md")
    shutil.copyfile(ROOT / "docs/WINDOWS.md", bundled / "WINDOWS.md")
    copy_licenses(bundled / "licenses")
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    compiler = (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Inno Setup 6/ISCC.exe"
    )
    if not compiler.is_file():
        raise RuntimeError("Install Inno Setup 6 to build the installer.")
    subprocess.run(
        [str(compiler), f"/DMyAppVersion={version}", str(ROOT / "packaging/static.iss")], check=True
    )
    shutil.make_archive(
        str(release / f"Static-{version}-Windows-x64-portable"), "zip", ROOT / "dist", "Static"
    )
    assets = sorted(
        [*release.glob(f"Static-{version}-*.exe"), *release.glob(f"Static-{version}-*.zip")]
    )
    if len(assets) != 2:
        raise RuntimeError("Expected one installer and one portable ZIP")
    with (release / "SHA256SUMS.txt").open("w", encoding="utf-8") as checksums:
        for path in assets:
            digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
            checksums.write(f"{digest}  {path.name}\n")
    shutil.copyfile(ROOT / "packaging/RELEASE_NOTES.md", release / "RELEASE_NOTES.md")
    print(f"Windows release {version} ready in {release}")


if __name__ == "__main__":
    main()
