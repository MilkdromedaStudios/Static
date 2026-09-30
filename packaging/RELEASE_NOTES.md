## Static for Windows

Download **Windows-x64-Setup.exe** for the installer, or unzip **Windows-x64-portable.zip** and run `Static.exe`. Windows 10 21H2 or newer / Windows 11, x64.

- Python and the desktop/browser runtime are included.
- First-run choice: cloud API key, Ollama, or another local model server.
- Windows Credential Manager stores API keys; model IDs and budgets are editable in Connections.
- Optional Ollama installation and model downloads always ask first. Installed local Ollama starts when needed.
- Minimize/close to the tray, click the tray icon for quick chat, or use its menu to open the full workspace or quit.
- Saved chat, tasks, files, dark mode, cost limits and media approvals use the same Python app.
- Optional start at login. Start menu/desktop shortcuts and a Windows Apps uninstaller are included.
- Uninstall removes saved API keys and startup registration. You choose whether to keep or delete workspace data. Ollama is separately managed.

The workflow tests the packaged app, installer, credential storage and uninstall before publishing. `SHA256SUMS.txt` contains the download checksums. This build is not code signed; Windows may show an unknown-publisher/SmartScreen prompt. Verify that you downloaded it from this repository.

See [Windows setup](https://github.com/MilkdromedaStudios/Static/blob/main/docs/WINDOWS.md) for usage, upgrades, data locations, and troubleshooting.
