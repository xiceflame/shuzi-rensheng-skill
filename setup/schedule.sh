#!/bin/bash
# No implicit recommended-set installation. Name tasks explicitly; preview first.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "${SHUZI_PYTHON:-python3}" "$HERE/schedule.py" "$@"
