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

## First-run provider setup (no unwanted downloads)

When you launch the Linux **Static Code** desktop app for the first time,
the terminal asks you to choose a provider before chatting. Options include
OpenAI API, Anthropic API, OpenAI-compatible HTTPS providers, an already
installed Claude Code CLI, or an already installed local Ollama model.
There is **no automatic Ollama installation or model download**.

The wizard requests the exact model ID, API endpoint when needed, a hidden
API key, and confirmation of cloud pricing. Model settings are shared with
the web UI through the same settings.json file. API keys are stored separately
in a private `credentials.env` under Static's data directory and are never
printed by `/models`.

Use `/setup` to change providers later, and `/models` to test the
connection. The existing web server also skips local model installation by
default; its `--setup-local-model` option explicitly opts into Ollama setup.

The terminal uses the same backend, conversations, tools, tasks, approvals,
MCP and media services as the web UI, but some web UI controls are not yet
exposed as dedicated interactive terminal screens.

## Custom API endpoints

Choose provider **3** for OpenAI-compatible chat/completions servers, or **6**
for Anthropic Messages-compatible endpoints. Enter the API base URL and exact
model identifier. Local HTTP endpoints (localhost, 127.0.0.1) are supported;
remote endpoints must use HTTPS. API keys are optional for custom servers.
Static will never pull a model during this setup. Custom services must implement
the selected protocol; arbitrary JSON APIs require an adapter.

Additional terminal commands: `/rename TITLE`, `/download ID PATH`,
`/task-done ID`, `/task-reopen ID`, `/media-refresh`, `/media-cancel ID`,
`/mcp-reload`, and `/budget USD`. Commands use the same backend endpoints
as the web application.

Files uploaded with `/upload PATH` are attached to the **next** chat message; they are not automatically sent until you submit that message.

## Experimental autonomous terminal modes

`/auto on` requires typing **AUTO APPROVE**. While enabled, Static automatically
accepts tool approval requests, including potentially destructive shell commands,
file edits, paid actions, and browser interactions. This bypasses approval prompts;
use only in a disposable workspace and turn it off with `/auto off`.
It resets when Static exits.

`/continuous on` requires a positive estimated API-spending cap and typing
**CONTINUE**. Once enabled, the next ordinary prompt bypasses the normal per-run AI step limit and starts successive runs,
continuing the same objective until completion, a failed run, Ctrl+C, or the
tracked cost cap. It is not an unattended daemon. Use `/continuous off`
before starting another prompt to disable it. Pricing and token usage estimates
may be incomplete for custom providers, so the cap is **not a guaranteed billing
limit**. Monitor your provider's own usage and billing limits.

The Linux launcher checks the repository's `main` branch on each launch,
fast-forwards the local checkout when possible, and reinstalls dependencies.
Updates are not applied to an already-running process. If offline, Static
launches the installed version. Running remote updates implicitly trusts
upstream code: review changes and use pinned releases for higher assurance.

## Saved conversations

Static Code saves chat messages to its local SQLite database automatically. It also remembers the active conversation ID and restores that chat on the next launch. Use `/new` to start a separate saved conversation, `/sessions` to list chats, `/resume ID` to switch, `/history` to view messages, and `/save` to explicitly mark the current chat as the one to reopen next time. `/save` does not export or back up the database.

## Combined automation mode

Use `/both on` to enable continuous execution and automatic tool approvals together. You must choose an estimated spending cap and type the exact confirmation `ENABLE BOTH`. This is high risk: tools may execute commands or change files without asking again, and the cap is an estimate, not a provider-side billing guarantee. Use `/both off` to disable both options, or `Ctrl+C` to stop the active run. Both switches default to off on each new terminal launch. The assistant is also prompted to explain its work and results more fully.
