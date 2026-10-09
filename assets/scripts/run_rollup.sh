#!/bin/bash
# 月/季汇总任务入口 —— 委托给引擎无关的 engine/run.sh（自动挑可用引擎）
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$HERE/engine/run.sh" rollup "$@"
