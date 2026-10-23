# Static interactive preview

The preview is a static export of Static's actual interface. `scripts/build_preview.py` copies only public UI assets, creates an HTML entry point for every page, adds `.nojekyll`, and replaces the live runtime flag with `mode: 'preview'` plus the DigitBox AI addresses below.

## Real answers with DigitBox AI

Pages can't run the Python API or hold model keys, so a visitor can connect their DigitBox account and the preview's chats get real replies from [DigitBox AI](https://digitbox.dev/ai) (`static_ai/static/hosted.js`):

1. **Connect AI** (top bar, the chat page or Connections) opens `https://digitbox.dev/ai/connect?origin=…&return=…`. The visitor signs in there and chooses **Allow**.
2. DigitBox sends them back with an AI-only token in the URL fragment (`#digitbox-ai=…`), which the preview stores in local storage and removes from the address bar. Fragments never reach a server. The token can only chat with DigitBox AI; it can't see the DigitBox account, and **Disconnect** deletes it.
3. Chats stream from `POST https://digitbox.pages.dev/api/ai/chat`. Free DigitBox accounts get a few messages a day with Nemotron 3.5 Lightning; DigitBox Pro is unlimited and adds Claude Haiku 5.5. The plan and model show in the top bar, the sidebar and the composer.

The model sees the conversation (not the example replies), the text of attached files, and the name and preferences from Settings. Files it writes as ```` ```markdown file=plan.md ```` blocks become Library files with download links. Create asks for text formats it can make (HTML for print-to-PDF, Markdown, CSV, SVG, OBJ, ICS, EML). There are no tools, web search or paid media generation in the preview.

The keys, plans and limits are configured on DigitBox: see [DIGITBOX_AI_SETUP.md](https://github.com/MilkdromedaStudios/DigitBox/blob/main/docs/DIGITBOX_AI_SETUP.md). DigitBox only issues tokens to `https://milkdromedastudios.github.io` unless its `AI_CONNECT_ORIGINS` adds more (for example `http://localhost:8080` to test a local preview).

Build options: `--ai-api` and `--ai-connect` point at another DigitBox deployment; `--no-ai` builds the example-only preview.

## Publish with GitHub Pages

1. Open the repository's **Settings → Pages**.
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. Open **Actions → Publish Static preview → Run workflow** on `main` (or rerun the latest run).
4. After the deploy job succeeds, use the `github-pages` environment URL. For this repository it is expected to be `https://milkdromedastudios.github.io/Static/`.

The workflow intentionally does not enable Pages with a privileged token. If Pages is absent or uses branch deployment, its build job still creates the complete preview artifact and emits the exact setup instruction; deployment waits for that setting. Once enabled, future main pushes rebuild and deploy automatically.

GitHub Pages serves HTML, CSS and JavaScript. It does not run this project's Python API. API credentials must never be added to Pages, Actions build variables, or the preview bundle. The build only needs Python's standard library.

## Run locally

```bash
python scripts/build_preview.py
python -m http.server 8080 --directory site
```

Visit `http://localhost:8080`. The export also works at `/Static/` and each `.html` route survives reload. Assets and navigation use relative URLs; conversation IDs use query parameters. There is no custom-domain or root-path assumption.

## What is interactive

- Home suggestions and the chat composer give real replies once DigitBox AI is connected, and labelled example replies until then.
- Tasks can be created, edited, marked complete, reopened and linked to sample runs.
- Create supports example documents, original vector art, a storyboard, real example OBJ geometry, unsent email drafts and calendar files. These are example outputs, not generated AI media.
- A media request demonstrates approval/decline without calling a provider or charging money.
- Library filters and downloads work. Text formats can be previewed safely.
- Skills, connection examples, names, preferences and budgets persist locally.
- Light/dark/system themes persist independently of the demo reset.
- Search finds tasks and conversations; mobile navigation works across all pages.
- The quick-chat button opens `mini.html`, with a compact conversation view, saved example chat, theme toggle and an expand link to the full conversation. The Windows desktop uses this same view with its live backend.

The `static-preview-v2` local-storage record contains fictional seed data plus your interactions; `static-digitbox-ai-v1` holds the DigitBox AI token and model choice. No telemetry or external assets are loaded. The demo adapter never calls `/api/`, and nothing outside the preview's own files is contacted until a visitor connects DigitBox AI; after that, only DigitBox AI's API. Preview uploads allow selected text files up to 500 KB; the Python app supports its wider upload policy. A reset in Settings restores the examples. Nothing synchronizes to the Python app.

## Production separation

`static_ai/static/runtime.js` selects live mode. `api.js` only imports `demo.js` when the builder explicitly selects preview mode. Server failures stay visible as server failures. No automatic preview fallback can hide a missing model, failed action or billing error. `hosted.js` (DigitBox AI) only switches on when the preview runtime carries its addresses; the Python app's runtime never does.

`tests/browser-smoke.cjs` serves the preview at a `/Static/` subpath, checks every entry point, exercises important controls, and asserts that it makes no API or external network requests until DigitBox AI is connected. Against a mocked DigitBox AI it checks connecting, streamed replies, file downloads, the free-plan limit and disconnecting. It also tests the real Python app against an isolated deterministic provider.
