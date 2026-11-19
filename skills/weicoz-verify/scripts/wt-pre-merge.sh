#!/bin/bash
# worktrunk pre-merge 钩子：仓库 AGENTS.md 有“## 验证约定”才跑通用门，否则静默放行。
# 用户级配置（~/.config/worktrunk/config.toml）：
#   [pre-merge]
#   verify-gate = "bash <本目录>/wt-pre-merge.sh {{ target }}"
# {{ target }} 是 wt merge 的合并目标分支（wt hook 文档：merge 操作的 target 变量）。
target="$1"
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
grep -q '^## 验证约定' "$root/AGENTS.md" 2>/dev/null || exit 0
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
base=()
[ -n "$target" ] && base=(--base "$target")
exec node "$here/verify-gate.mjs" --project "$root" "${base[@]}"
