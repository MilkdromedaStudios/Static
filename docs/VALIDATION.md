# Validation for 0.1.0

Checked during the initial build:

- **30 backend tests passed** on Python 3.12. They exercise the actual FastAPI app and SQLite store against a deterministic HTTP model/media provider. Covered flows include chat persistence, file and PDF/DOCX generation, safe downloads, upload scope, specialist delegation, real OBJ mesh outputs, one-use media approval, denial, cancellation, local-only mode, step limits, budget race protection, source caching and request boundaries.
- **Real Chromium browser workflow passed** at desktop and mobile sizes: navigation, connection test, skill toggles, a coordinator/tool/final-answer run, file download, reload/reopen persisted chat, file gallery and horizontal-overflow checks. No page JavaScript errors were observed. The test provider is separate from the production code.
- Desktop and phone screenshots were inspected; the workspace screenshot in this repository is from the running application.
- Python lint/format checks, JavaScript syntax checking and Git whitespace checks passed.
- A wheel was built and checked for all static UI assets. Locked dependencies and that wheel installed successfully into a clean Python environment; the installed app initialized correctly.

Not claimed by these checks:

- Live AI answer quality, local model performance, and paid image/video/3D provider behavior. No real API keys or paid calls were used.
- Live public web retrieval in this restricted build environment. Public-network DNS was unavailable to the hardened direct-fetch client. Search/parser/IP/redirect behavior is covered by tests, but live sites may block requests.
- A local Docker build/run or Windows/macOS launch. Recipes and launch scripts are included; CI covers additional Python versions when GitHub Actions runs.

Provider error messages, setup steps and these boundaries are documented so deployment failures are actionable rather than silently replaced with demo output.
