# Static for Windows

## Install or use the portable download

Open the repository's [latest release](https://github.com/MilkdromedaStudios/Static/releases/latest). Choose the `Windows-x64-Setup.exe` installer. It installs for your Windows user, adds a Start menu entry, offers a desktop shortcut, and appears in Windows **Settings → Apps → Installed apps**. Windows 10 21H2 or later / Windows 11 on x64 is supported. Native ARM64 builds are not included.

The ZIP alternative contains the same app and runtime. Extract the whole `Static` folder before running `Static.exe`; keep `_internal` next to the executable. Portable describes the program files: both downloads keep saved work in your Windows user data folder.

**Python is bundled.** Installing this download does not install or modify system Python. Ollama is optional. The source launchers still ask before installing missing Python, and the desktop's native setup asks before installing Ollama or pulling a model.

These releases are not code signed. Windows may show SmartScreen or an unknown publisher warning. Download only from this repository; checksums are in `SHA256SUMS.txt`. Publisher signing can be added when a signing certificate is available.

## Choose your AI

The first-run dialog offers:

| Mode | What you provide | What Static starts |
| --- | --- | --- |
| API key | Tool-capable model ID, OpenAI-compatible HTTPS base URL, key, verified per-million-token rates | Its own Python service; Ollama is skipped |
| Ollama | Local model ID, default `qwen3:4b` | An installed Ollama service; installation and model download require separate yes prompts |
| Another local server | Loopback base URL and exact tool-capable model ID, e.g. an LM Studio server | Its own service; start the other model server yourself |

API providers differ in model IDs, prices and token fields. Select `max_tokens` or `max_completion_tokens` according to your provider. Enter the actual current prices; confirm zero only for a free endpoint. The app's Connections page supports multiple models, specialist routing, model tests and media profiles.

Change the active chat connection later using **Static → AI setup**. Finish or stop active tasks before switching. This selects a single coordinator profile; configure multiple profiles in Connections afterward. **Static → API keys** edits the keys referenced by saved models, plus `BRAVE_API_KEY` and `REPLICATE_API_TOKEN` for search and media. New keys take effect immediately. Leave blank to retain a key, or select Remove. Credentials are stored in **Windows Credential Manager**, scoped to this workspace. Only key variable names go into JSON files.

Cloud chat uses your provider's OpenAI-compatible API. Media uses your Replicate token and the profiles you configure; a chat key does not also pay for unrelated media/search providers. Documents, exported files and procedural geometry run in the bundled app. Budgets, tool approvals and the account-action boundaries described in README still apply.

## Tray and quick chat

- Minimize or close the full window to keep Static in the tray by default. The icon may be under Windows' hidden-icons arrow.
- Click the tray icon to toggle quick chat. Double-click to open the workspace. Right-click for the menu.
- Quick chat uses real saved conversations and the same selected model/budgets. Enter sends; Shift+Enter inserts a line break. Use the expand button to open that chat in the full app. Paid action approvals are reviewed in the full workspace.
- Use **Quit Static** to stop the app's service. Active tasks are stopped; completed chats and files stay saved. An installer/model download must finish before quitting.
- **Options** toggles minimizing to the tray, keeping quick chat on top, and start at Windows login. Login startup is off initially. If the system tray is unavailable, the app stays reachable from the normal taskbar.
- Opening Static again restores the same instance. `Static.exe --mini` opens quick chat. Start-at-login opens minimized.
- Downloads show a native Save dialog. External links open in your normal browser. The embedded browser displays only the local workspace, with an automatically supplied, per-launch authentication token.

## Data, updates and uninstall

Data: `%LOCALAPPDATA%\StaticAI` — SQLite chats/tasks, generated files, model settings, desktop preferences, browser theme/history, and `desktop.log`. The desktop uses a remembered loopback port to preserve browser settings. If that port is occupied, it chooses another. Static does not listen on your network.

Updates: **Static → Downloads and updates** opens the latest GitHub release. Run the newer installer; it reuses the install directory and keeps your data. There is no silent updater or background download. Source users can migrate by copying their existing data directory here while both versions are closed; keep the artifacts folder with the database. See MIGRATION.md for the older Buns database.

Uninstall using Windows Installed apps or the Start menu's **Uninstall Static**. The uninstaller closes the app, removes its installed files, shortcuts, start-at-login entry and saved Windows API keys. It asks whether to also delete your chats, generated files and preferences; **No keeps your work**. A silent uninstall keeps the workspace by default. Reinstallation needs you to enter provider keys again. Ollama, its downloaded models, and external/system Python are shared software and remain installed. Uninstall them through Windows separately if you want them removed.

For a portable download, quit Static, run `Static.exe --cleanup-credentials`, then delete the extracted folder. Delete `%LOCALAPPDATA%\StaticAI` separately if you want to remove its saved work. Advanced `--data-dir` workspaces are outside the installer's default data cleanup and must be managed separately.

## Build and release

On Windows with Python 3.12 and Inno Setup 6:

```powershell
python -m pip install -r requirements-dev.lock -r requirements-desktop.lock
python -m pip install --no-deps -e .
python -m static_ai.desktop
python scripts/build_windows.py
python scripts/test_windows_package.py
```

The package test requires a fresh test Windows account with no existing Static workspace. It runs the frozen desktop with a fixture provider, tests both source modes in the native setup, an authenticated embedded chat, tray menu/window behavior and Credential Manager. It installs the real installer, launches that installed app, then uninstalls it and checks removal of credentials/startup while preserving a sample data file. It performs no real model calls or Ollama/Python installs. The data-deletion confirmation and Windows' actual tray positioning still benefit from a manual check on the target PC.

**Release Windows app** runs automatically when the project version or its workflow changes on `main`, and can be run manually in Actions. It tests, packages, builds the installer, verifies install/uninstall, and publishes the EXE, portable ZIP and SHA256 checksums as `vX.Y.Z`. Existing versions are kept intact. Bump both `pyproject.toml` and `static_ai/__init__.py` to publish another version. Releases have their own write permission; regular checks and pull requests cannot publish.

Build evidence is uploaded as `static-windows-test-results`, and binaries as `static-windows-release`. Qt/Python license texts and third-party notices are shipped with the installer and ZIP. PyInstaller's folder build keeps the Qt libraries separate, so users can replace compatible LGPL libraries and rebuild from the source. The packaging scripts and dependency snapshot are available in this repository.
