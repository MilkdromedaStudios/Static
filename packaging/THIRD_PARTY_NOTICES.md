# Third-party software in Static for Windows

Static's source is MIT licensed; see LICENSE.txt. The Windows download bundles Python and dynamically linked Qt libraries with the server dependencies. Package license texts from the build environment are included in `licenses/`. Libraries and their license files remain separately accessible in the `_internal` folder.

- **CPython** — Python Software Foundation license. Source: https://www.python.org/downloads/source/
- **Qt / PySide6 / Shiboken** — Qt's LGPLv3 / GPLv3 / commercial licensing terms. Static uses the LGPL option. Source and corresponding version archives: https://download.qt.io/official_releases/qt/ and https://download.qt.io/official_releases/QtForPython/
- **Qt WebEngine / Chromium** — LGPL and component-specific permissive licenses. The package includes Qt WebEngine's notices and applicable dependency licenses. Sources: https://code.qt.io/cgit/qt/qtwebengine.git/ and https://chromium.googlesource.com/chromium/src/
- **PyInstaller** — GPL with the bootloader exception, which permits distributing the bundled application under its own license. Source: https://github.com/pyinstaller/pyinstaller
- **FastAPI, Starlette, Uvicorn, HTTPX, Pydantic, python-dotenv, python-multipart, python-docx, Beautiful Soup, Pillow, pypdf, lxml, ReportLab and supporting Python packages** — see each corresponding bundled license.

Build and replacement instructions are in WINDOWS.md and the public Static repository. Static does not prohibit reverse engineering for debugging modifications to the LGPL libraries. The installer does not rely on a Qt commercial license. Do not remove the applicable license texts when redistributing the portable folder.
