#!/bin/bash
# All shell adapters use the same validated configuration loader as Python.
_SHUZI_RUNTIME="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/assets/scripts/shuzi_runtime.py"
cfg_get() { "${SHUZI_PYTHON:-python3}" "$_SHUZI_RUNTIME" get "$1"; }
cfg_key() { "${SHUZI_PYTHON:-python3}" "$_SHUZI_RUNTIME" key "$1"; }
cfg_env() { cfg_get "$1"; }
cfg_on() { [ "$(cfg_get "$1.enabled")" = "true" ]; }
