#!/bin/bash
# Python runner owns configuration, exit codes, locks and execution receipts.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "${SHUZI_PYTHON:-python3}" "$HERE/run.py" "$@"
