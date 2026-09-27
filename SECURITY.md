# Security and operating boundaries

Static 0.2 is a single-user personal workspace. Bind to `127.0.0.1` by default. For access over a network, the CLI requires a random token of at least 24 characters; restrict `STATIC_ALLOWED_HOSTS`, use HTTPS through a trusted reverse proxy and keep the service private. All API routes, artifacts and settings share that token. There are no independent user accounts or tenant isolation. Do not host this as a public anonymous service.

External websites/files are untrusted evidence. The coordinator is instructed not to treat them as instructions, and sensitive capabilities are structurally absent: no shell execution, payment handling, authenticated browser sessions or messaging. Prompt instructions alone are not a security sandbox. Do not enable tools that expand these boundaries without a stronger isolation design.

- Model keys are read from server environment variables. UI settings contain key names and presence booleans, never values. The CLI can load a local `.env`; it is git-ignored.
- Public-web tools allow HTTP(S), ports 80/443 only. All resolved IPs must be global. Requests pin a validated IP while retaining the hostname for Host/TLS, and revalidate every redirect. System proxies are deliberately disabled for public fetching to avoid bypassing these checks. Use a deployment with direct public DNS/network access.
- Operator-configured model endpoints are trusted configuration and may point to a local model server. Do not give untrusted people the workspace token: they could change those endpoints.
- Model text is rendered through a small DOM-only Markdown formatter, not HTML. Artifact downloads use attachment disposition and binary content type. No external scripts/fonts are loaded. API mutations require a custom client header and same-origin browser requests. Host checks reduce DNS rebinding risk.
- Uploads allow selected text/PDF extensions and at most 5 MB. Text extraction supports the first 20 PDF pages and 30,000 characters. It is not antivirus scanning; only upload files you trust. PDF parsing and document generation run in the server process.
- Spending controls are estimates based on configured rates and provider usage, not a substitute for billing limits at the provider. No automatic retry of paid submissions. An uncertain submission retains its reservation and requires operator investigation.
- Databases, conversations and artifacts are stored unencrypted on the host. Use disk encryption and protect/back up the data directory. Deleting a conversation is not yet exposed; retention is operator-managed while the service is stopped.
- Replicate job IDs are durable, but downloads can fail after provider URLs expire. Keep the service running through generation and download important outputs.

If reporting a problem, omit API keys, access tokens, `.env`, databases, personal prompts and generated files. Share a minimal reproduction and the relevant error class. Rotate any accidentally exposed provider key immediately.

The public GitHub Pages preview contains only UI code and fictional example data. Its browser-local uploads/preferences are not synchronized to a server. Do not place provider keys in it. Static does not render uploaded HTML/SVG as active documents; downloads are attachments and text previews use textContent. The reset action affects only preview storage.

Existing BUNS_AUTH_TOKEN and BUNS_ALLOWED_HOSTS environment variables remain fallbacks during migration; STATIC_ equivalents take precedence. The SQLite backup migration retains the legacy database. Protect both copies with the same filesystem controls.
