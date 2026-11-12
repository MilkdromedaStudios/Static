# Static CLI (Windows, Linux, macOS)

This is a terminal interface to the **same Static backend** as the desktop and web app.
It uses your configured model providers, conversations, tasks, files, skills, MCP
connections, approval workflow, and budget limits. No second server is needed.

## Install

Requires Python 3.11 or newer.

```bash
git clone https://github.com/MilkdromedaStudios/Static.git
cd Static
python -m pip install -e .
static
```

On Windows, use `py -m pip install -e .` if `python` is not on PATH.
If the `static` executable is not on PATH, run `python -m static_ai.terminal`.

For real-browser interaction, additionally run:

```bash
python -m pip install -e ".[browser]"
python -m playwright install chromium
```

On Linux, Chromium may require system libraries. See Playwright's official
dependency instructions (`python -m playwright install --with-deps chromium`).

## Usage

```text
static
static --mode local
static --data-dir ./data
static --conversation EXISTING_CONVERSATION_ID
static -p "Research public documentation for Python packaging"
```

Interactive commands: `/help`, `/exit`, `/new`, `/conversations`,
`/tasks`, `/skills`, `/files`, and `/mode economy|local`.

The CLI opens the FastAPI app **in-process**, without binding a network port.
The CLI and web app can use the same data directory, but do not run them
concurrently against the same workspace while an agent is active.

Browser tools: `browser_navigate` reads a rendered public webpage;
`browser_interact` clicks, fills, presses keys, and selects options using
CSS selectors. Each interaction asks for explicit one-time approval. Local and
private IP destinations are blocked. Never automate sensitive transactions.

### Known limitations

This is an initial integration, not a fully tested standalone binary. Browser
sessions last for the CLI process, screenshots are not implemented, and some
sites may block automation. Interactive website actions require the optional
Playwright dependency and Chromium installation. The existing Static tools
still do not provide arbitrary local shell execution or unrestricted code edits.

## Static Code terminal experience

Install the interactive prompt dependency:

```bash
python -m pip install -e ".[code,browser]"
python -m playwright install chromium
static
```

The terminal now provides a persistent bottom status bar, command completion,
multiline editing (Esc+Enter), local prompt history, saved conversation
switching, and live tool activity. Conversations and messages persist in the
existing SQLite database. Use `/sessions` to list them, `/resume ID` to
continue one, and `/history` to review messages.

For local project coding, set `STATIC_CODE_ROOT` to your repository path
(or start Static in the project directory). The `code_list`, `code_read`,
and `code_write` skills operate inside this workspace. Every write requires
explicit approval for the exact file and content. There is no unrestricted
shell execution, git commit/push automation, or automatic test execution yet.
The optional browser tools remain approval-gated.

This is an incremental Claude Code-style experience, not feature parity.

## One-command setup (recommended, including Raspberry Pi 5)

Run from the checked-out Static repository using Python 3.11+:

```bash
python3 bootstrap.py
```

On Windows use `py bootstrap.py`. The launcher automatically creates
`.venv`, installs Static and the interactive terminal dependencies, and
starts the terminal. No manual `pip install`, activation, or virtualenv
management is required. Later starts reuse the environment. Run
`python3 bootstrap.py --update` after updating source code to reinstall.

For Raspberry Pi OS use 64-bit Python 3.11+ and an available network connection
for initial package installation. Browser automation is optional and not
installed by default; Chromium can be resource-intensive. The terminal does
not launch a browser or web server and caps command output to 16 KiB.

The `code_run` tool executes an argv array (not shell strings) in the
workspace after explicit approval for each command. Each process has a
maximum 120-second timeout and no stdin. Use `STATIC_CODE_ROOT` to specify
the project directory; otherwise the launcher uses the directory from
which it was started. **This is not an OS sandbox**: approved commands
have the user's normal filesystem/network permissions. Only approve
commands you understand, and do not run Static as root.

## Linux desktop app: one-command install

From a Linux terminal (including Raspberry Pi OS with a desktop):

```bash
curl -fsSL https://raw.githubusercontent.com/MilkdromedaStudios/Static/main/install-linux.sh | bash
```

The installer clones Static into `~/.local/share/static-code`, creates a
private virtual environment, installs dependencies, adds the `static-code`
command to `~/.local/bin`, and registers a **Static Code** application in
your desktop's application menu. Clicking it opens a terminal running Static
Code. Project files default to `~/StaticWorkspace`. No root permissions
or global Python packages are required.

Requirements: Git, curl, Python 3.11+, Python venv/ensurepip, internet on
first install, and a supported graphical terminal emulator. If `curl`
is missing, install it using your distro package manager. For safety, you
can inspect the installer before running it.

To update, rerun the same command. On machines without a graphical desktop,
use `~/.local/bin/static-code` from an existing terminal.
