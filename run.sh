#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(command -v python3 || echo "/usr/bin/python3")"

exec "$PYTHON_BIN" "$SCRIPT_DIR/dynamic_island.py" "$@"
