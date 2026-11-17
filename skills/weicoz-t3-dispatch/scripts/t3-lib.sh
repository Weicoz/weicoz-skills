#!/usr/bin/env bash
# t3-*.sh 共用：调用 t3 CLI 并过滤 `Database migration history diverges` 警告块。
# 由各脚本 source，不单独执行。兼容 macOS 自带 bash 3.2。
#
# 两条实测结论（v0.1.10-nightly.20261112.4580）：
# 1. t3 的 WARN/ERROR 日志写 **stdout**，不写 stderr。所以过滤对象是两路合并后的文本，
#    只过滤 stderr 会漏。调用方统一 `2>&1`，由 t3_call 处理。
# 2. 该警告由 t3 内部的 logWarning 副作用打印，不影响命令退出码。实测 `thread list`
#    退出 1 时伴随的是真实错误（如 SecretStoreSecureError），不是警告本身。
#    所以下面只在**成功**时过滤文本；失败时把捕获内容原样打印，退出码原样返回。

# 过滤 stdin 里的 migration 警告块：从含关键短语的日志行起，按花括号配平跳过整块。
# 上限 200 行兜底，避免日志里花括号不配平时吞掉后续真实错误。
t3_strip_noise() {
  awk '
    BEGIN { skip = 0; depth = 0; taken = 0 }
    skip == 0 {
      if ($0 ~ /Database migration history diverges/) {
        skip = 1; taken = 0
        depth = gsub(/\{/, "{") - gsub(/\}/, "}")
        if (depth <= 0) { skip = 0 }
        next
      }
      print
      next
    }
    {
      taken++
      depth += gsub(/\{/, "{") - gsub(/\}/, "}")
      if (depth <= 0 || taken >= 200) { skip = 0 }
      next
    }
  '
}

# 成功：把过滤后的文本打到 stdout；失败：把原始捕获原样打到 stderr，stdout 留空。
# 退出码与 t3 一致，调用方的 `if !`、`||`、pipefail 判断不受影响。
t3_call() {
  local raw rc
  raw=$(command t3 --log-level none "$@" 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    printf '%s\n' "$raw" | t3_strip_noise
  else
    printf '%s\n' "$raw" >&2
  fi
  return "$rc"
}

# 同 t3_call，但失败也不打印：给 `set -e` 下的尽力而为调用用（如吊销令牌）。
t3_call_quiet() {
  local raw rc
  raw=$(command t3 --log-level none "$@" 2>&1)
  rc=$?
  [ "$rc" -eq 0 ] && printf '%s\n' "$raw" | t3_strip_noise
  return "$rc"
}
