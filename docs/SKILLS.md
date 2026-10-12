# Add a skill

Skills are trusted Python code installed by the workspace owner. The model cannot download, install or enable code by itself. Start with a small tool and an explicit Pydantic argument schema.

```python
# static_ai/skills/calculator.py
from pydantic import Field
from static_ai.config import StrictModel
from static_ai.skills.base import Skill

class Add(StrictModel):
    numbers: list[float] = Field(min_length=1, max_length=100)

async def add(ctx, args):
    return {"sum": sum(args.numbers)}

def register(registry):
    registry.add(Skill(
        "numbers_add",
        "Add a list of numbers exactly as supplied. Does not fetch data.",
        "Utilities", Add, add,
    ))
```

Import the new register function in `static_ai/skills/__init__.py` and call it in `create_registry()`. Restart Static; the tool appears in Skills and its schema is supplied to the coordinator. Add a focused integration test for observable behavior and permission boundaries.

A handler receives `Context`: the current conversation/run IDs, mode, store, configuration, providers, artifacts and media service. Use `ctx.artifacts.save(...)` for binary artifacts or `ctx.artifacts.document(...)` for documents. Use `fetch_public` for user-supplied public URLs, not an unrestricted HTTP client. Tool descriptions should say what the tool actually does, its limitations and whether its results contain untrusted content.

## Extending permissions

A skill with `approval=True` must also supply `terms(ctx, args) -> (terms, cost)`. The engine persists a one-use approval holding the arguments plus those terms, pauses the run, and when approved re-computes the terms and refuses to act if any differ (for example, a changed media profile or MCP server configuration). The approval is consumed before the external action. `media_generate` binds its Replicate profile and cost reservation; MCP tools bind the server, tool name and a fingerprint of the server's configuration. This is **not** a generic permission framework for purchases, messaging or browser actions: bind every intended recipient, input, destination and cost in the terms, and test denial, duplicate requests, restart recovery, ambiguous submission failures and cancellation.

Do not simply add a checkout POST, arbitrary shell executor, unrestricted browser, or downloaded plugin to the tool registry. Those require their own authorization and isolation model. Shopping in this release is research, calculation and seller-link handoff.

## Connecting other language models

Each model connection has a `provider`: `openai` (the OpenAI-compatible `/chat/completions` protocol, the default), `anthropic` (the Claude Messages API) or `claude_code` (the local Claude Code CLI). A coordinator must support tools. Specialists can use a tool-free model. Add multiple configurations with role assignments to route a writer to one model and the coordinator to another.

- Anthropic: `provider="anthropic"`, `https://api.anthropic.com/v1`, an exact Claude model ID and a key variable such as `ANTHROPIC_API_KEY`. Static converts tools to `input_schema`, tool calls to `tool_use` and results to `tool_result` blocks. Test connection lists models; dated IDs match their alias.
- Claude Code: `provider="claude_code"`, a model alias (`sonnet`, `opus`, `haiku`) or full name, cloud with confirmed prices. No base URL. Static runs `claude -p --output-format json --no-session-persistence --tools "" --strict-mcp-config --disable-slash-commands` in an empty temporary folder, sends the conversation as JSON on stdin and the system prompt as a file, and (for a coordinator) requires structured output listing tool calls. Static then runs those tools itself. `ANTHROPIC_API_KEY` and Static's other secrets are removed from its environment unless the connection names a key variable. Test connection runs only `claude --version` and `claude auth status`.

- Ollama: `http://localhost:11434/v1` (or `http://ollama:11434/v1` inside Compose).
- LM Studio: `http://localhost:1234/v1`, using a tool-capable model where needed.
- OpenAI: `https://api.openai.com/v1`, with the exact model ID available to your account. Use `max_completion_tokens` where required.
- OpenRouter: `https://openrouter.ai/api/v1`, with an exact provider/model ID. Check that the chosen endpoint supports tools.
- Other servers: a compatible HTTP(S) base URL, model ID, token limit parameter, pricing and environment-variable key name.

No model names/prices are assumed to remain current. Use provider documentation and Test connection. A successful `/models` check verifies connectivity and listing only; a real tool-calling conversation is the final compatibility test.

## MCP servers

Static is a small [Model Context Protocol](https://modelcontextprotocol.io) client. It reads `mcp.json` in the data directory when it starts and when you select **Connections → Reload servers** (blocked while a task is active). Each entry in `mcpServers` is either a local command (`command`, `args`, `env`, `cwd`), run over stdio, or a Streamable HTTP server (`url`, `headers`); the legacy SSE transport is not supported. Unknown keys from other clients are ignored. Static-specific keys:

- `approval`: `writes` (default) asks before tools without the `readOnlyHint` annotation; `always` asks before every call; `never` trusts the server completely.
- `disabled: true` keeps an entry without starting it. `timeout` is the per-request limit in seconds (default 60).
- `${NAME}` or `${NAME:-default}` in a command, argument, `env`, URL or header reads the server environment. A missing variable marks the server as needing attention.

After `initialize`, Static lists up to 64 tools per server (skipping tools whose schema is over 16 KB) and registers each as `mcp__<server>__<tool>` with the server's input schema, category `MCP`, and a description noting that results are untrusted data. Arguments are passed through; the server validates them. Text results are returned to the coordinator (up to 24,000 characters), images and audio are saved as conversation files, and `isError` results become tool errors. Tool-list change notifications from stdio servers refresh the list. Local servers receive only a basic environment (`PATH`, `HOME`, locale, temp and proxy variables) plus their configured `env`. HTTP servers follow the same HTTPS rule as cloud models; servers on other hosts are remote and are unavailable in local-only mode.

The web interface shows status and reloads servers but cannot write `mcp.json`: adding a program that runs on the host is an operator action. Every enabled tool's schema is sent with each coordinator request and counts toward the 100 KB request limit, so switch off tools you do not need in Skills.

## Media profile examples

Profiles contain `model`, `prompt_field`, `inputs`, `reserve_usd`.

- An official text-to-image model may use `owner/model`, `prompt_field="prompt"` and model-supported defaults such as an aspect ratio.
- A community model needs `owner/model:64-character-version`; Static posts the version to `/predictions`.
- Some 3D models accept text; others require an image URL. For an image-to-3D model, configure image input defaults and a real supported prompt field, or set the prompt field to its image URL field and ask Static to supply that URL. Static does not upload private images to Replicate or guess input schemas.

Keep the default input set small. Check actual price and schema before choosing the reservation. An empty profile is disabled. Paid API secrets belong in environment variables, not these JSON defaults.

Primary protocol references:

- https://docs.ollama.com/api/openai-compatibility
- https://replicate.com/docs/reference/http
- https://replicate.com/docs/topics/predictions/create-a-prediction
- https://api-dashboard.search.brave.com/app/documentation/web-search

## Included portable action skills

- `calendar_create`: timezone-aware start/end, escaped RFC 5545 text, UTF-8 line folding; returns an `.ics` artifact to import.
- `email_draft`: subject/body and optional recipient; rejects header newlines and returns an unsent `.eml`. No outbound mail capability.
- `table_analyze`: conversation-scoped CSV artifact; row counts and finite numeric column statistics over the bounded text sample.

Use `args.model_dump(mode="json")` when persisting typed arguments containing dates or other non-JSON Python values. The engine does this for activity events. Avoid putting secrets in tool arguments or results.
