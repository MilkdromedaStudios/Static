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

In this release, `approval=True` is specifically implemented for `media_generate`; it is **not** a generic permission framework for purchases, messaging or browser actions. To add another side-effecting tool, first extend the approval preparation/validation flow in `engine.py` to bind all intended recipients, inputs, destinations and costs. Persist a one-use approval before the external action. Test denial, duplicate requests, restart recovery, ambiguous submission failures and cancellation.

Do not simply add a checkout POST, arbitrary shell executor, unrestricted browser, or downloaded plugin to the tool registry. Those require their own authorization and isolation model. Shopping in this release is research, calculation and seller-link handoff.

## Connecting other language models

All language models use the OpenAI-compatible `/chat/completions` protocol. A coordinator must support function tools. Specialists can use a tool-free model. Add multiple configurations with role assignments to route a writer to one model and the coordinator to another.

- Ollama: `http://localhost:11434/v1` (or `http://ollama:11434/v1` inside Compose).
- LM Studio: `http://localhost:1234/v1`, using a tool-capable model where needed.
- OpenAI: `https://api.openai.com/v1`, with the exact model ID available to your account. Use `max_completion_tokens` where required.
- OpenRouter: `https://openrouter.ai/api/v1`, with an exact provider/model ID. Check that the chosen endpoint supports tools.
- Other servers: a compatible HTTP(S) base URL, model ID, token limit parameter, pricing and environment-variable key name.

No model names/prices are assumed to remain current. Use provider documentation and Test connection. A successful `/models` check verifies connectivity and listing only; a real tool-calling conversation is the final compatibility test.

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
