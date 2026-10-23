#!/usr/bin/env bash
# 把 claude-agents/ 下的 agent 定义软链到 Claude Code 用户级 agents 目录。
# Claude Code 只从 ~/.claude/agents/、项目 .claude/agents/、插件 agents/ 等位置注册 subagent，
# skill 目录里的文件不会被自动注册，所以需要这一步。
set -euo pipefail

src="$(cd "$(dirname "$0")/../claude-agents" && pwd -P)"
dest="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/agents"
mode="${1:---apply}"
fail=0

mkdir -p "$dest"
for f in "$src"/*.md; do
  name="$(basename "$f")"
  target="$dest/$name"
  if [[ -L "$target" && "$(readlink "$target")" == "$f" ]]; then
    printf '已就绪: %s\n' "$name"
  elif [[ -e "$target" && ! -L "$target" ]]; then
    printf '跳过（已存在同名普通文件，请人工处理）: %s\n' "$target" >&2
    fail=1
  elif [[ "$mode" == "--check" ]]; then
    printf '缺失或指向错误: %s\n' "$target" >&2
    fail=1
  else
    ln -sfn "$f" "$target"
    printf '已链接: %s -> %s\n' "$target" "$f"
  fi
done

(( fail == 0 ))
