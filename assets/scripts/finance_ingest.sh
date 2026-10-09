#!/bin/bash
# 财务增量任务入口 —— 委托给引擎无关的 engine/run.sh（自动挑可用引擎）
# 用法: bash finance_ingest.sh [--engine openclaw|claude|codex|api|ollama|manual]
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$HERE/engine/run.sh" finance-ingest "$@"
