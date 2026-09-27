# How Buns works

Buns is a **single-user, local-first Python application**, not a hosted AI service. FastAPI serves an offline-capable static interface and a JSON API. SQLite persists conversations, public activity events, run state, approval decisions, cost reservations, media jobs and file metadata. Actual files live in an opaque-ID artifact directory. There is no JavaScript build step, CDN dependency or telemetry.

## One turn

1. The API saves the user message and creates one run per conversation. Up to two runs execute concurrently; up to eight can be queued/running in process.
2. The coordinator receives the last 16 user/assistant messages and a schema for each enabled skill. Tool history is kept within the current run. It chooses its next action using native tool calling.
3. Tool arguments are validated with Pydantic. Tools have explicit Python handlers; model output is never executed as Python or shell commands.
4. Each model request reserves an estimated upper cost before sending. The router chooses the cheapest eligible, configured model for the requested role. Local-only mode excludes remote models and paid search/media.
5. A specialist receives one bounded task and reference context. It has no tools and cannot recursively delegate. Its result goes back to the coordinator, which can turn it into a file or combine it with research.
6. A paid media call pauses the run. The approval binds to the specific arguments and media profile. Approval is consumed before submission and cannot be replayed. Declining creates a tool result without invoking the media API.
7. The final answer and files persist. The UI polls public task events; it does **not** display private chain-of-thought or stream tokens that have not arrived.

## Files and asynchronous media

File tools create TXT, Markdown, JSON, CSV, HTML, DOCX and PDF. The OBJ builder creates cube, sphere and cylinder geometry locally. Generative images/video/3D use Replicate's predictions API and require the operator to configure a model's actual input schema. Media jobs are synced every 10 seconds and downloadable outputs are copied into local artifacts. A job may outlive its chat run. Cancelling a run does not cancel a previously submitted prediction; use Files → Cancel. Unknown submissions remain marked unknown; check the provider dashboard before resubmitting.

Media supports up to eight HTTPS outputs per prediction, at most 50 MB per output. Formats that need multiple referenced files may need packaging into a provider ZIP; Buns does not automatically rewrite glTF external references. Provider output URLs can expire; keep Buns running or use Refresh jobs promptly.

## Persistence and recovery

`data/settings.json` stores non-secret settings; `data/buns.db` stores workflow data. API secrets are environment variables (the CLI loads a local `.env`). The application is designed for **one Uvicorn worker**. Run additional independent workspaces with separate data directories rather than multiple workers on the same database.

After a server restart, queued/running work is marked interrupted instead of replaying side effects. Pending approvals can still be approved/declined. Known media prediction IDs are polled again. Settings changes are blocked while any run is queued, working or waiting for approval, preventing configuration changes from silently changing an approved action.

Only the last 16 user/assistant messages feed the next task; old tool transcripts are not re-injected automatically. Use an explicit follow-up summary for long projects. A 100 KB serialized model-input limit prevents unbounded context growth. No persistent semantic memory or embeddings are claimed.

## Cost semantics

Model routing uses `input_per_million + 2 × output_per_million` as a simple estimate. This is a cost heuristic, not a guarantee that the cheapest model can solve every task. Configure roles to send difficult tasks to a stronger model when needed. There is no automatic paid fallback after errors.

The ledger atomically checks both the run and UTC daily budgets and reserves before external calls. Input bytes plus framing overhead provide a conservative token estimate; output uses the configured token maximum. Reported prompt/completion usage replaces that reservation. Missing usage or uncertain request outcomes retain estimates. Media/search keep operator-defined reservations rather than inventing a per-model price.

**These are application estimates, not enforceable provider invoices.** Wrong rates, unusual tokenization, provider-side extras, asynchronous runtime billing, or price changes can make actual charges differ. Enter current rates, confirm them in the UI, and set provider-side billing limits. No API call should be assumed free merely because an API key exists. Local hardware/electricity cost is not included.

## Source layout

- `buns/app.py`: HTTP API, lifespan, authentication, same-origin checks.
- `buns/engine.py`: coordinator and approval state machine.
- `buns/providers.py`: model selection, OpenAI-compatible request adapter, token accounting.
- `buns/skills/`: typed skill registry and built-in tools.
- `buns/network.py`: public GET requests with DNS/IP and redirect validation.
- `buns/media.py`: Replicate submission and persistent job synchronization.
- `buns/artifacts.py`: scoped storage and format generation.
- `buns/db.py`: transactional SQLite storage and cost reservations.
- `buns/static/`: the complete responsive interface.
- `tests/`: fake-provider contract tests and a browser workflow test. No test calls a paid model.
