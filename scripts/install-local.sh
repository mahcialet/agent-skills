#!/usr/bin/env bash
set -euo pipefail

# Compatibility only: argument parsing and source checks live in Python.
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to install a local Skill." >&2
  exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "${script_dir}/install_local_cli.py" "$@"
