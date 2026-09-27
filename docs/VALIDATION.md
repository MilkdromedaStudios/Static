# Validation for Static 0.2.0

Checked during the rebrand and workflow update:

- **37 backend tests pass on Python 3.12.** The actual FastAPI app and SQLite store run against deterministic model/media HTTP providers. Coverage includes chat persistence, tool orchestration, file/PDF/Word exports, scoped uploads, real OBJ geometry, specialist routing, one-use approvals, denial, cancellation, local-only mode, limits, atomic budget reservations, web request boundaries and source caching.
- New regression cases cover saved goals/checklists and completion/reopen, calendar timezone conversion/escaping/UTF-8 folding, unsent email exports and header injection rejection, scoped finite CSV analysis, preference context, legacy database/auth migration, page entry points and explicit preview builds.
- **The Chromium end-to-end suite passes for both live and preview modes.** It tests real model-settings requests against the isolated fixture, 13 skill toggles, coordinator/tool/final-answer flow, file downloads, reload persistence, saved-task execution, eight Pages routes at a repository subpath, preview approvals, file/text previews, search, persistent preferences, safe text rendering, light/dark themes and phone navigation. Both themes are checked for horizontal overflow across all eight pages at 390 × 844.
- Preview network requests are asserted to contain only its own static assets. No `/api/` or third-party requests are made by its interactions. No JavaScript page errors were observed.
- Desktop light/dark and phone screenshots were inspected. `docs/static-light.png` and `docs/static-dark.png` show the interactive preview with fictional sample content; `docs/static-mobile-dark.png` shows the phone layout after the test interactions.
- A clean wheel build includes every static asset and excludes the legacy Python package.
- Python lint/format, JavaScript syntax, and Git whitespace checks are included in the verification workflow. GitHub Actions runs the backend on Python 3.11, 3.12 and 3.13, and saves browser screenshots as artifacts.

These checks use no real model keys and incur no provider charges. They do not establish live AI answer quality, model speed, provider availability or paid image/video/3D generation quality. Public-web parsing and DNS/redirect restrictions have contract tests; live public sites can block or rate-limit requests. Windows/macOS launch and a local Docker build/run were not exercised in this environment.

GitHub Pages publication is a separate deployment status. The build workflow produces a downloadable preview even when Pages is disabled. The URL is live only after the repository enables Pages with GitHub Actions and a deploy job succeeds. See `PREVIEW.md`.
