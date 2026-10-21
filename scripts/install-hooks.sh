#!/usr/bin/env bash
# 安装 Git hooks：把 core.hooksPath 指向仓库内的 .githooks/。
#
# 用法：
#   ./scripts/install-hooks.sh          # 安装
#   ./scripts/install-hooks.sh --remove # 卸载（恢复默认 hooks 目录）
#
# 为什么用 core.hooksPath：.git/hooks/ 不进版本库，新克隆拿不到；
# .githooks/ 随仓库分发，装一次即可。

set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$repo"

if [[ "${1:-}" == "--remove" ]]; then
  git config --unset core.hooksPath 2>/dev/null || true
  printf '已卸载：core.hooksPath 恢复默认（.git/hooks）\n'
  exit 0
fi

if [[ ! -d .githooks ]]; then
  printf '缺少 .githooks 目录，无法安装。\n' >&2
  exit 1
fi

chmod +x .githooks/* 2>/dev/null || true
git config core.hooksPath .githooks

printf '已安装：core.hooksPath = .githooks\n'
printf '提交前会自动执行 scripts/validate-skills.sh --no-links\n'
