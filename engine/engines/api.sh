#!/bin/bash
# Credentials are read from configured environment variables inside Python,
# never passed through argv or evaluated as shell code.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "${SHUZI_PYTHON:-python3}" "$HERE/../api-agent.py"
