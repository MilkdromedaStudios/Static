#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python_cmd=""
find_python() {
  local candidate
  for candidate in python3.12 python3.13 python3.14 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
      python_cmd="$candidate"
      return 0
    fi
  done
  return 1
}

if ! find_python; then
  echo "Static needs Python 3.11 or newer."
  if [[ ! -t 0 ]]; then
    echo "Install Python from https://www.python.org/downloads/ and restart this script."
    exit 1
  fi
  read -r -p "Install Python now using your system package manager? [y/N] " answer
  case "${answer,,}" in y|yes) ;; *) echo "Install Python from https://www.python.org/downloads/ to continue."; exit 1 ;; esac
  if [[ "$(uname -s)" == Darwin ]] && command -v brew >/dev/null 2>&1; then
    brew install python@3.12
  elif command -v apt-get >/dev/null 2>&1; then
    if (( EUID == 0 )); then prefix=(); elif command -v sudo >/dev/null 2>&1; then prefix=(sudo); else echo "Install Python from https://www.python.org/downloads/"; exit 1; fi
    "${prefix[@]}" apt-get update
    "${prefix[@]}" apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null 2>&1; then
    if (( EUID == 0 )); then prefix=(); elif command -v sudo >/dev/null 2>&1; then prefix=(sudo); else echo "Install Python from https://www.python.org/downloads/"; exit 1; fi
    "${prefix[@]}" dnf install -y python3 python3-pip
  else
    echo "No supported package manager found. Install Python from https://www.python.org/downloads/ and retry."
    exit 1
  fi
  if ! find_python; then
    echo "Python 3.11+ is not available after installation. Check the version or reopen the terminal, then rerun start.sh."
    exit 1
  fi
fi

# Repair a broken environment without touching its installed packages or data.
if [[ ! -x .venv/bin/python ]]; then
  for name in python python3 python3.11 python3.12 python3.13 python3.14; do
    if [[ -L ".venv/bin/$name" ]]; then rm ".venv/bin/$name"; fi
  done
  "$python_cmd" -m venv --copies .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.lock
.venv/bin/python -m pip install --disable-pip-version-check --no-deps -e .
exec .venv/bin/python -m static_ai "$@"
