#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "${SHUZI_PYTHON:-python3}" "$HERE/schedule.py" --platform macos "$@"
