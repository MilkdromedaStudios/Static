# Upgrading from Buns to Static

The assistant, interface, repository, icon and documentation are now **Static**. The Python package is `static_ai`, the distribution is `static-ai-workspace`, and the CLI is `static-ai` (or `python -m static_ai`). This avoids naming a Python package simply `static`.

## Local installation

1. Stop the old server and back up your entire existing data directory.
2. Update the repository remote to `https://github.com/MilkdromedaStudios/Static.git`, pull the new version, and run the setup script again (or reinstall with `pip install --no-deps -e .`).
3. Launch Static with the **same data directory**, for example `python -m static_ai --data-dir /path/to/existing/data`.
4. Rename your environment variables to `STATIC_DATA_DIR`, `STATIC_AUTH_TOKEN` and `STATIC_ALLOWED_HOSTS` when convenient. Existing `BUNS_` versions of those three variables remain supported as fallbacks. Explicit `STATIC_` values take precedence. A model's custom `key_env` is unchanged; retain the named provider variable or update the connection setting.

On first launch, if `buns.db` exists and `static.db` does not, Static copies the database using SQLite's backup API, including committed WAL contents. It stages the copy in a temporary file and renames it only after completion. The original is retained for rollback. The new database adds the tasks table; existing chats, runs, approvals, costs and artifact records remain.

Keep the artifact directory at the same absolute path: stored artifact locations are absolute and must remain inside that workspace's artifact root. Renaming the repository folder is optional; do not move a relative `data` directory unintentionally. If you need to relocate data, keep a full backup and update artifact paths deliberately while the server is stopped.

New display-name/preferences fields have defaults, so older `settings.json` files continue to load. Browser access tokens use a new session-storage key, so token-protected workspaces must be unlocked again. Never run both old and new servers against the same data directory.

## Docker

Docker Compose service/volume names changed. **Do not start a blank volume and assume your previous work is gone.** Keep the old volume and explicitly reuse it:

1. Stop the old Compose stack, without `-v`, before replacing its configuration.
2. Find the existing data volume with `docker volume ls` (commonly `<old-project>_buns-data`). Back it up.
3. Set `STATIC_DATA_VOLUME` in `.env` to that exact existing volume name, and set `STATIC_AUTH_TOKEN` for the new Compose service.
4. Start the new stack. The same files mount at `/app/data`, and the SQLite migration runs automatically.

Fresh installations default to the explicitly named `static-workspace-data` volume. Model weights remain in the existing Ollama volume only if the Compose project name also remains the same; when moving project folders, retain the prior project name with Compose's `-p` option or reuse/migrate the Ollama volume deliberately.

## API and extensions

Imports move from `buns.*` to `static_ai.*`. Browser/API writes now require `X-Static-Client: web`. Static assets are served at `/assets/`. Settings schemas gain `display_name` and `preferences`; saved goals use `/api/tasks` and its start/edit endpoints. The model protocol, artifact IDs, SQLite run records, and media approvals retain their existing semantics.
