# Static interactive preview

The preview is a static export of Static's actual interface. `scripts/build_preview.py` copies only public UI assets, creates an HTML entry point for every page, adds `.nojekyll`, and replaces the live runtime flag with `mode: 'preview'`.

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

- Home suggestions and the chat composer open scripted sample conversations.
- Tasks can be created, edited, marked complete, reopened and linked to sample runs.
- Create supports example documents, original vector art, a storyboard, real example OBJ geometry, unsent email drafts and calendar files. These are example outputs, not generated AI media.
- A media request demonstrates approval/decline without calling a provider or charging money.
- Library filters and downloads work. Text formats can be previewed safely.
- Skills, connection examples, names, preferences and budgets persist locally.
- Light/dark/system themes persist independently of the demo reset.
- Search finds tasks and conversations; mobile navigation works across all pages.
- The quick-chat button opens `mini.html`, with a compact conversation view, saved example chat, theme toggle and an expand link to the full conversation. The Windows desktop uses this same view with its live backend.

The `static-preview-v2` local-storage record contains fictional seed data plus your interactions. No telemetry or external assets are loaded. The demo adapter never calls `/api/`. Preview uploads allow selected text files up to 500 KB; the Python app supports its wider upload policy. A reset in Settings restores the examples. Nothing synchronizes to the Python app.

## Production separation

`static_ai/static/runtime.js` selects live mode. `api.js` only imports `demo.js` when the builder explicitly selects preview mode. Server failures stay visible as server failures. No automatic preview fallback can hide a missing model, failed action or billing error.

`tests/browser-smoke.cjs` serves the preview at a `/Static/` subpath, checks every entry point, exercises important controls, and asserts that it never makes API or external network requests. It also tests the real Python app against an isolated deterministic provider.
