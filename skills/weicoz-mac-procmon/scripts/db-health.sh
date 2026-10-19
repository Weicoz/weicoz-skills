#!/usr/bin/env bash
# mac-procmon 数据库与采集健康检查（只读）。
# 环境变量：PROCMON_BIN 覆盖二进制路径；PROCMON_STATE_DIR 覆盖状态目录。
set -uo pipefail

BIN="${PROCMON_BIN:-procmon}"
STATE_DIR="${PROCMON_STATE_DIR:-$HOME/.local/state/mac-procmon}"
DB="$STATE_DIR/procmon.db"

command -v sqlite3 >/dev/null 2>&1 || {
  echo "错误：未找到 sqlite3，无法读取数据库统计。"
  echo "macOS 自带 /usr/bin/sqlite3，请检查 PATH。"
  exit 1
}

q() { sqlite3 "$DB" "$1" 2>/dev/null; }

echo "== mac-procmon 健康检查 =="
if command -v "$BIN" >/dev/null 2>&1; then
  echo "二进制     : $BIN ($("$BIN" --version 2>/dev/null | head -1))"
else
  echo "二进制     : 未找到 $BIN（可用 PROCMON_BIN 指定，或把仓库二进制加入 PATH）"
fi

[ -f "$DB" ] || { echo "数据库     : 不存在 $DB（先运行 $BIN start）"; exit 0; }

STATE="$("$BIN" status 2>/dev/null | sed -n 's/.*Daemon State[[:space:]]*:[[:space:]]*//p' | sed 's/[[:space:]]*(PID.*//')"
echo "启动状态   : ${STATE:-未知}"
echo "数据库     : $DB"
echo "文件大小   : $(( $(stat -f%z "$DB") / 1048576 )) MB"
[ -f "$DB-wal" ] && echo "WAL        : $(( $(stat -f%z "$DB-wal") / 1048576 )) MB"

echo
echo "-- 页与回收 --"
echo "auto_vacuum: $(q 'PRAGMA auto_vacuum;')   (2 = INCREMENTAL；0 = 未启用，incremental_vacuum 为空操作)"
echo "freelist   : $(q 'PRAGMA freelist_count;') 页"
echo "page_size  : $(q 'PRAGMA page_size;') 字节"

echo
echo "-- 数据窗口 --"
echo "proc_samples : $(q 'SELECT COUNT(*) FROM proc_samples;') 行"
echo "proc_lifetime: $(q 'SELECT COUNT(*) FROM proc_lifetime;') 行"
echo "sys_snapshot : $(q 'SELECT COUNT(*) FROM sys_snapshot;') 行"
echo "incidents    : $(q 'SELECT COUNT(*) FROM incidents;') 条"
q "SELECT '时间范围     : ' || datetime(MIN(ts),'unixepoch','localtime') || ' → ' || datetime(MAX(ts),'unixepoch','localtime') FROM proc_samples;"
q "SELECT '窗口小时数   : ' || printf('%.1f', (MAX(ts)-MIN(ts))/3600.0) FROM proc_samples;"
q "SELECT '超保留窗行数 : ' || COUNT(*) FROM proc_samples WHERE ts < strftime('%s','now')-86400;"

LAST="$("$BIN" status 2>/dev/null | sed -n 's/.*Last Snapshot[[:space:]]*:[[:space:]]*//p')"
echo "最新快照     : ${LAST:-无}"
if [ -n "${LAST:-}" ]; then
  LAST_EPOCH="$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST" +%s 2>/dev/null || echo "")"
  [ -n "$LAST_EPOCH" ] && echo "快照年龄     : $(( ( $(date +%s) - LAST_EPOCH ) / 60 )) 分钟"
fi

echo
echo "-- 判定 --"
AV="$(q 'PRAGMA auto_vacuum;')"
FL="$(q 'PRAGMA freelist_count;')"
STALE="$(q "SELECT COUNT(*) FROM proc_samples WHERE ts < strftime('%s','now')-86400;")"
if [ "${AV:-0}" = "0" ]; then
  echo "WARN auto_vacuum=0：删除的页不会归还。运行 \"$BIN restart\" 触发一次 VACUUM 转 INCREMENTAL。"
else
  echo "OK   auto_vacuum=INCREMENTAL。"
fi
if [ "${FL:-0}" -gt 500 ]; then
  echo "WARN freelist=$FL 页（约 $(( FL * 4 / 1024 )) MB 空闲）：库是高水位，运行 \"$BIN restart\" 回收。"
else
  echo "OK   无显著空闲页。"
fi
if [ "${STALE:-0}" -gt 0 ]; then
  echo "WARN $STALE 行超过 24 小时保留窗：守护停跑过；重启后下一个五分钟窗口剪枝。"
else
  echo "OK   无超窗数据。"
fi
exit 0
