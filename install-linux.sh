#!/usr/bin/env bash
# Install Static Code for the current Linux user without sudo.
set -Eeuo pipefail

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/static-code"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
# Dedicated profile: do not change the user's normal LXTerminal colors or font.
TERMINAL_PROFILE_DIR="$HOME/.config/lxterminal"
WORK_DIR="$HOME/StaticWorkspace"
REPO_URL="https://github.com/MilkdromedaStudios/Static.git"

fail() { printf 'Static Code installer: %s\n' "$*" >&2; exit 1; }
command -v git >/dev/null || fail "git is required (install it using your distribution package manager)."
command -v python3 >/dev/null || fail "Python 3.11+ is required."
python3 -c 'import sys; sys.exit(sys.version_info < (3,11))' || fail "Python 3.11+ is required."
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || fail "Python venv/ensurepip missing (on Debian/Raspberry Pi OS install python3-venv)."

mkdir -p "$(dirname "$APP_DIR")" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$WORK_DIR"
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
# Check upstream on each launch. Only fast-forward; keep existing install if offline.
# No model downloads. Updates to application code require trusted upstream.
if command -v git >/dev/null 2>&1 && [[ -d "$APP_DIR/.git" ]]; then
  if timeout 12 git -C "$APP_DIR" fetch -q --depth 1 origin main 2>/dev/null; then
    CURRENT="$(git -C "$APP_DIR" rev-parse HEAD)"
    LATEST="$(git -C "$APP_DIR" rev-parse FETCH_HEAD)"
    if [[ "$CURRENT" != "$LATEST" ]]; then
      echo "[Static] Update found. Installing latest version..."
      if git -C "$APP_DIR" merge --ff-only FETCH_HEAD && (cd "$APP_DIR" && python3 -c 'import bootstrap; bootstrap.install(force=True)'); then
        echo "[Static] Updated. Launching..."
      else
        echo "[Static] Update failed; check installation before continuing." >&2
        exit 1
      fi
    fi
  fi
fi
exec "$APP_DIR/.venv/bin/python" -m static_ai.terminal --data-dir "$APP_DIR/data" "$@"
EOF
chmod +x "$BIN_DIR/static-code"

# A separate, readable Pi desktop profile. Preserve customizations on repeat
# installs; only touch the profile owned by this launcher when creating it.
mkdir -p "$TERMINAL_PROFILE_DIR"
if [[ ! -f "$TERMINAL_PROFILE_DIR/lxterminal-StaticCode.conf" ]]; then
  cat > "$TERMINAL_PROFILE_DIR/lxterminal-StaticCode.conf" <<'EOF'
[general]
fontname=Monospace 13
bgcolor=rgb(11,17,32)
fgcolor=rgb(231,241,255)
color_preset=Custom
bgalpha=65535
scrollback=5000
cursorblinks=false
disallowbold=false
hidescrollbar=false
hidemenubar=true
geometry_columns=100
geometry_rows=34
EOF
fi

# GUI launcher: use a named, isolated LXTerminal profile on Raspberry Pi OS.
# --no-remote prevents LXTerminal reusing an already-open light themed window.
cat > "$BIN_DIR/static-code-desktop" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
BIN="$HOME/.local/bin/static-code"
if command -v lxterminal >/dev/null 2>&1; then
  exec lxterminal --no-remote --profile=StaticCode --geometry=100x34 --title="Static Code" --command="$BIN"
elif command -v xfce4-terminal >/dev/null 2>&1; then
  exec xfce4-terminal --disable-server --title="Static Code" --geometry=100x34 --command="$BIN"
elif command -v xterm >/dev/null 2>&1; then
  exec xterm -fa "DejaVu Sans Mono" -fs 13 -geometry 100x34 -bg "#0B1120" -fg "#E7F1FF" -e "$BIN"
elif command -v gnome-terminal >/dev/null 2>&1; then
  exec gnome-terminal -- "$BIN"
elif command -v konsole >/dev/null 2>&1; then
  exec konsole -e "$BIN"
elif command -v x-terminal-emulator >/dev/null 2>&1; then
  exec x-terminal-emulator -e "$BIN"
else
  echo "No supported terminal emulator found. Run $BIN from a terminal." >&2
  exit 1
fi
EOF
chmod +x "$BIN_DIR/static-code-desktop"

cat > "$ICON_DIR/static-code.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
<rect x="8" y="8" width="112" height="112" rx="24" fill="#172334"/>
<path d="M32 40l25 24-25 24" fill="none" stroke="#62dfc0" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M67 88h29" stroke="#fff" stroke-width="9" stroke-linecap="round"/>
</svg>
EOF

cat > "$DESKTOP_DIR/static-code.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Static Code
Comment=Terminal AI coding assistant
Exec=$BIN_DIR/static-code-desktop
Icon=static-code
Terminal=false
Categories=Development;Utility;
StartupNotify=true
Keywords=Static;AI;Coding;Terminal;
EOF
chmod 644 "$DESKTOP_DIR/static-code.desktop"
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
printf '\nStatic Code installed!\nOpen "Static Code" from your Linux application menu.\n'
printf 'Terminal command: %s/static-code\nWorkspace: %s\n' "$BIN_DIR" "$WORK_DIR"
printf 'If the command is not on PATH, run: %s/static-code\n' "$BIN_DIR"
