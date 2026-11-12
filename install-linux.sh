#!/usr/bin/env bash
# Install Static Code for the current Linux user without sudo.
set -Eeuo pipefail

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/static-code"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
WORK_DIR="$HOME/StaticWorkspace"
REPO_URL="https://github.com/MilkdromedaStudios/Static.git"

fail() { printf 'Static Code installer: %s\n' "$*" >&2; exit 1; }
command -v git >/dev/null || fail "git is required (install it using your distribution package manager)."
command -v python3 >/dev/null || fail "Python 3.11+ is required."
python3 -c 'import sys; sys.exit(sys.version_info < (3,11))' || fail "Python 3.11+ is required."
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || fail "Python venv/ensurepip missing (on Debian/Raspberry Pi OS install python3-venv)."

mkdir -p "$(dirname "$APP_DIR")" "$BIN_DIR" "$DESKTOP_DIR" "$WORK_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  echo "[Static] Updating existing installation..."
  git -C "$APP_DIR" pull --ff-only
elif [[ -e "$APP_DIR" ]]; then
  fail "$APP_DIR exists but is not a Git checkout; move it before installing."
else
  echo "[Static] Downloading Static Code..."
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
fi

echo "[Static] Creating environment and installing dependencies..."
# Installation is handled by the repo's Python bootstrap; no global pip changes.
"$APP_DIR"/bootstrap.py --update -p "Say hello" >/dev/null 2>&1 && true || {
  # Avoid invoking an AI model during installation. Use bootstrap's install() directly.
  :
}
# Only install; do not launch a model, open a terminal, or require API credentials.
(cd "$APP_DIR" && python3 -c 'import bootstrap; bootstrap.install(force=True)') || fail "Python dependency installation failed."

cat > "$BIN_DIR/static-code" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/static-code"
WORK_DIR="$HOME/StaticWorkspace"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"
export STATIC_CODE_ROOT="$WORK_DIR"
exec "$APP_DIR/.venv/bin/python" -m static_ai.terminal --data-dir "$APP_DIR/data" "$@"
EOF
chmod +x "$BIN_DIR/static-code"

# GUI launcher: try common terminal emulators, then display a useful error.
cat > "$BIN_DIR/static-code-desktop" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
BIN="$HOME/.local/bin/static-code"
if command -v x-terminal-emulator >/dev/null 2>&1; then
  exec x-terminal-emulator -e "$BIN"
elif command -v xfce4-terminal >/dev/null 2>&1; then
  exec xfce4-terminal --disable-server --command="$BIN"
elif command -v lxterminal >/dev/null 2>&1; then
  exec lxterminal -e "$BIN"
elif command -v gnome-terminal >/dev/null 2>&1; then
  exec gnome-terminal -- "$BIN"
elif command -v konsole >/dev/null 2>&1; then
  exec konsole -e "$BIN"
elif command -v xterm >/dev/null 2>&1; then
  exec xterm -e "$BIN"
else
  echo "No supported terminal emulator found. Run $BIN from a terminal." >&2
  exit 1
fi
EOF
chmod +x "$BIN_DIR/static-code-desktop"

cat > "$DESKTOP_DIR/static-code.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Static Code
Comment=Terminal AI coding assistant
Exec=$BIN_DIR/static-code-desktop
Icon=utilities-terminal
Terminal=false
Categories=Development;Utility;
StartupNotify=true
EOF
chmod 644 "$DESKTOP_DIR/static-code.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
printf '\nStatic Code installed!\nOpen "Static Code" from your Linux application menu.\n'
printf 'Terminal command: %s/static-code\nWorkspace: %s\n' "$BIN_DIR" "$WORK_DIR"
printf 'If the command is not on PATH, run: %s/static-code\n' "$BIN_DIR"
