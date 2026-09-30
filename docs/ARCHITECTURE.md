# How Static works

Static is a **single-user, local-first Python application**, not a hosted AI service. FastAPI serves an self-contained static interface and a JSON API. SQLite persists conversations, public activity events, run state, approval decisions, cost reservations, media jobs and file metadata. Actual files live in an opaque-ID artifact directory. There is no JavaScript build step, CDN dependency or telemetry.

## One turn

1. The API saves the user message and creates one run per conversation. Up to two runs execute concurrently; up to eight can be queued/running in process.
2. The coordinator receives the last 16 user/assistant messages and a schema for each enabled skill. Tool history is kept within the current run. It chooses its next action using native tool calling.
3. Tool arguments are validated with Pydantic. Tools have explicit Python handlers; model output is never executed as Python or shell commands.
4. Each model request reserves an estimated upper cost before sending. The router chooses the cheapest eligible, configured model for the requested role. Local-only mode excludes remote models and paid search/media.
5. A specialist receives one bounded task and reference context. It has no tools and cannot recursively delegate. Its result goes back to the coordinator, which can turn it into a file or combine it with research.
6. A paid media call pauses the run. The approval binds to the specific arguments and media profile. Approval is consumed before submission and cannot be replayed. Declining creates a tool result without invoking the media API.
7. The final answer and files persist. The UI polls public task events; it does **not** display private chain-of-thought or stream tokens that have not arrived.

## Files and asynchronous media

File tools create TXT, Markdown, JSON, CSV, HTML, DOCX and PDF. The OBJ builder creates cube, sphere and cylinder geometry locally. Generative images/video/3D use Replicate's predictions API and require the operator to configure a model's actual input schema. Media jobs are synced every 10 seconds and downloadable outputs are copied into local artifacts. A job may outlive its chat run. Cancelling a run does not cancel a previously submitted prediction; use Library → Cancel. Unknown submissions remain marked unknown; check the provider dashboard before resubmitting.

Media supports up to eight HTTPS outputs per prediction, at most 50 MB per output. Formats that need multiple referenced files may need packaging into a provider ZIP; Static does not automatically rewrite glTF external references. Provider output URLs can expire; keep Static running or use Refresh status promptly.

## Persistence and recovery

`data/settings.json` stores non-secret settings; `data/static.db` stores workflow data. API secrets are environment variables (the CLI loads a local `.env`). The application is designed for **one Uvicorn worker**. Run additional independent workspaces with separate data directories rather than multiple workers on the same database.

After a server restart, queued/running work is marked interrupted instead of replaying side effects. Pending approvals can still be approved/declined. Known media prediction IDs are polled again. Settings changes are blocked while any run is queued, working or waiting for approval, preventing configuration changes from silently changing an approved action.

Only the last 16 user/assistant messages feed the next task; old tool transcripts are not re-injected automatically. Use an explicit follow-up summary for long projects. A 100 KB serialized model-input limit prevents unbounded context growth. No persistent semantic memory or embeddings are claimed.

## Cost semantics

Model routing uses `input_per_million + 2 × output_per_million` as a simple estimate. This is a cost heuristic, not a guarantee that the cheapest model can solve every task. Configure roles to send difficult tasks to a stronger model when needed. There is no automatic paid fallback after errors.

The ledger atomically checks both the run and UTC daily budgets and reserves before external calls. Input bytes plus framing overhead provide a conservative token estimate; output uses the configured token maximum. Reported prompt/completion usage replaces that reservation. Missing usage or uncertain request outcomes retain estimates. Media/search keep operator-defined reservations rather than inventing a per-model price.

**These are application estimates, not enforceable provider invoices.** Wrong rates, unusual tokenization, provider-side extras, asynchronous runtime billing, or price changes can make actual charges differ. Enter current rates, confirm them in the UI, and set provider-side billing limits. No API call should be assumed free merely because an API key exists. Local hardware/electricity cost is not included.

## Source layout

- `static_ai/app.py`: HTTP API, lifespan, authentication, same-origin checks.
- `static_ai/engine.py`: coordinator and approval state machine.
- `static_ai/providers.py`: model selection, OpenAI-compatible request adapter, token accounting.
- `static_ai/skills/`: typed skill registry and built-in tools.
- `static_ai/network.py`: public GET requests with DNS/IP and redirect validation.
- `static_ai/media.py`: Replicate submission and persistent job synchronization.
- `static_ai/artifacts.py`: scoped storage and format generation.
- `static_ai/db.py`: transactional SQLite storage and cost reservations.
- `static_ai/static/`: the complete responsive interface.
- `tests/`: fake-provider contract tests and a browser workflow test. No test calls a paid model.

## Goals, preferences and portable actions

The tasks table links a saved objective and checklist to a conversation. Starting a task creates a normal bounded run; plan_update also updates the saved checklist. User edits and completion are explicit. Tasks persist, but are not a scheduler, a cron system or a background VM. Running work can continue after the browser closes while the server process remains alive.

Explicit user preferences are stored in settings and supplied to model calls as context. No implicit personal-data mining, vector memory or cross-account access is implemented. Calendar and email skills create portable files only. Calendar timestamps must include offsets and are serialized in UTC with escaped/folded iCalendar lines. Email headers reject line breaks; drafts carry X-Unsent. CSV analysis uses bounded local text extraction and finite numeric values, without eval or code execution.

## Interface and preview

The optional `static_ai.desktop` shell uses PySide6 and an embedded Qt WebEngine view. A single instance owns an authenticated loopback Uvicorn service and shared browser profile. Native AI setup selects a cloud, Ollama, or other local connection; Windows Credential Manager stores provider keys. A tray icon opens the compact chat page or the full workspace. The bundled runtime is built with PyInstaller; an Inno Setup installer provides per-user installation, upgrade, credential cleanup and optional data removal. The release workflow tests the frozen app and install/uninstall before publishing versioned binaries.

The same vanilla JavaScript shell serves Home, Conversation, Tasks, Create, Library, Skills, Connections and Settings. The Python app serves their .html entry points; the Pages builder emits real copies for static hosting. Theme tokens use CSS variables, and a synchronous startup script restores the saved theme before paint. All icons and artwork are code-native assets.

The shell launchers detect Python before invoking it, offer installation through system package managers, and install locked dependencies in a project virtual environment. The CLI checks whether its configured local model points at the local Ollama port. If so, it checks the local API, starts an installed Ollama server when needed, and asks before downloading a missing model. With a cloud-only model, no Ollama probe or startup is performed. A first-run cloud model can be configured with `STATIC_CHAT_*` environment variables and a named API-key variable; the pricing confirmation is explicit. Existing JSON settings always win. Installation failure leaves the web app available for Connections setup.

The live adapter calls the authenticated same-origin API. The explicit preview adapter contains only fictional seed data and deterministic examples in browser storage; it never makes model/API requests. A failing live request cannot activate the demo. See PREVIEW.md for the deployment and storage model.
