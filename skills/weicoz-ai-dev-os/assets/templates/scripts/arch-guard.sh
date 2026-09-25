#!/usr/bin/env bash
# Architecture Guard — 把 docs/constitution.md 里能 grep 的条款变成检查。
# 安装时替换路径与模式，禁止原样带着其它项目的 import 规则。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIOLATIONS=0

echo "Running Architecture Guard..."

report_violation() {
    local rule="$1"
    local msg="$2"
    local file="$3"
    echo "VIOLATION [$rule] in $file: $msg"
    VIOLATIONS=$((VIOLATIONS + 1))
}

# --- 在此按本仓 C4/C1 填写 P0 grep ---
# 示例（删除无关示例后再启用）：
# if [ -d "$ROOT_DIR/src/components" ]; then
#   while read -r line; do
#     [ -z "$line" ] && continue
#     file=$(echo "$line" | cut -d: -f1)
#     report_violation "C4-NoDbInComponents" "UI 不得直接 import 数据库" "$file"
#   done < <(grep -rnE "from ['\"]@/db|getDb\(" "$ROOT_DIR/src/components" 2>/dev/null || true)
# fi

# C6 行数 warning（可按仓调整）
if [ -d "$ROOT_DIR/src" ]; then
    while read -r file; do
        [ -z "$file" ] && continue
        lines=$(wc -l < "$file" | tr -d ' ')
        if [ "$lines" -gt 600 ]; then
            echo "WARNING [C6-LineLimit] $file exceeds 600 lines ($lines)"
        fi
    done < <(find "$ROOT_DIR/src" -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.py" \) 2>/dev/null || true)
fi

echo ""
if [ "$VIOLATIONS" -gt 0 ]; then
    echo "Arch-Guard failed with $VIOLATIONS P0 violation(s)."
    exit 1
fi

echo "Arch-Guard passed."
exit 0
