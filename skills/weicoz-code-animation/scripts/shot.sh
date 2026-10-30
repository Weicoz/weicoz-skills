#!/usr/bin/env bash
# 用 Chrome headless 按 ?t= 截一帧静帧（核验风格与画面用）。
#
# 用法：
#   ./scripts/shot.sh <html 路径> <秒> <输出 png> [宽] [高] [缩放]
#   ./scripts/shot.sh --verify <html 路径> <秒>        # 同一 t 截两次比哈希，验确定性
#   ./scripts/shot.sh --probe <html 路径> [t1] [t2]   # 多点采样，验画面真的随 t 变化
#   ./scripts/shot.sh demo/index.html 5.7 /tmp/a.png
#
# 前提：页面支持 ?t=<秒> 定格渲染（输出契约见 references/RENDER.md）。
# Chrome 路径优先取 $CHROME_BIN，其次 $CHROME_PATH，再找 macOS 常见安装位置，最后查 PATH。
set -euo pipefail

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; }

verify=0; probe=0
case "${1:-}" in
  --verify) verify=1; shift ;;
  --probe)  probe=1; shift ;;
esac

# 探测时间点：默认取 4 个，覆盖慢开场（0–2 秒静止也至少有一个点落在动的段落里）
PROBE_TIMES=(0.2 1.0 3.0 6.0)

if [[ "$probe" -eq 1 ]]; then
  html="${1:-}"
  [[ -n "$html" ]] || { usage; exit 2; }
  shift || true
  if [[ $# -ge 2 ]]; then
    if [[ $# -gt 4 ]]; then
      echo "自定义时刻最多 4 个，收到 $# 个" >&2
      exit 2
    fi
    PROBE_TIMES=("$@")
  fi
  at="${PROBE_TIMES[0]}"
elif [[ "$verify" -eq 1 ]]; then
  if [[ $# -lt 2 ]]; then usage; exit 2; fi
  html="$1"; at="$2"
else
  if [[ $# -lt 3 ]]; then usage; exit 2; fi
  html="$1"; at="$2"; out="$3"
fi
if [[ "$probe" -eq 1 || "$verify" -eq 1 ]]; then
  w=1920; h=1080; scale=1
else
  w="${4:-1920}"; h="${5:-1080}"; scale="${6:-1}"
fi

[[ -f "$html" ]] || { echo "找不到页面：$html" >&2; exit 1; }

check_time() {
  [[ "$1" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "时间必须是秒数（如 3.3）：$1" >&2; exit 1; }
}
if [[ "$probe" -eq 1 ]]; then
  for v in "${PROBE_TIMES[@]}"; do check_time "$v"; done
else
  check_time "$at"
fi
[[ "$w" =~ ^[0-9]+$ ]] && (( w >= 16 )) || { echo "宽度必须是整数像素：$w" >&2; exit 1; }
[[ "$h" =~ ^[0-9]+$ ]] && (( h >= 16 )) || { echo "高度必须是整数像素：$h" >&2; exit 1; }

find_chrome() {
  local v
  for v in "${CHROME_BIN:-}" "${CHROME_PATH:-}"; do
    [[ -n "$v" && -x "$v" ]] && { echo "$v"; return; }
  done
  local c
  for c in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"; do
    [[ -x "$c" ]] && { echo "$c"; return; }
  done
  command -v google-chrome || command -v chromium || command -v chromium-browser || true
}

chrome="$(find_chrome)"
if [[ -z "$chrome" ]]; then
  cat >&2 <<'EOF'
错误：未找到 Chrome / Chromium / Edge。
请安装上述任一浏览器，或指定路径：
  export CHROME_BIN="/path/to/Chrome"
EOF
  exit 1
fi

abs="$(cd "$(dirname "$html")" && pwd)/$(basename "$html")"
mk_url() {
  python3 -c 'import sys,urllib.parse as u; print("file://" + u.quote(sys.argv[1]) + "?t=" + sys.argv[2])' "$abs" "$1"
}

# 每次截图用独立 profile：并行渲染时互不干扰。
shoot() {
  local dest="$1" tdisp="${2:-$at}" profile
  profile="$(mktemp -d "${TMPDIR:-/tmp}/anim-shot-XXXXXX")"
  mkdir -p "$(dirname "$dest")"
  "$chrome" \
    --headless=new \
    --enable-unsafe-swiftshader \
    --hide-scrollbars \
    --mute-audio \
    --no-first-run \
    --no-default-browser-check \
    --disable-extensions \
    --user-data-dir="$profile" \
    --force-device-scale-factor="$scale" \
    --window-size="$w,$h" \
    --virtual-time-budget=4000 \
    --run-all-compositor-stages-before-draw \
    --screenshot="$dest" \
    "$(mk_url "$tdisp")" >/dev/null 2>&1 || true
  rm -rf "$profile"
  if [[ ! -s "$dest" ]]; then
    echo "截图失败：${dest}（t=${tdisp}）" >&2
    echo "排查：直接用浏览器打开 ${abs}?t=${tdisp}；或检查 \$CHROME_BIN 是否可执行（当前：${chrome}）" >&2
    return 1
  fi
}

if [[ "$probe" -eq 1 ]]; then
  pdir="$(mktemp -d "${TMPDIR:-/tmp}/anim-probe-XXXXXX")"
  trap 'rm -rf "$pdir"' EXIT
  hashes=()
  for tv in "${PROBE_TIMES[@]}"; do
    shoot "$pdir/p_$tv.png" "$tv" || exit 1
    hashes+=("$(shasum "$pdir/p_$tv.png" | cut -d' ' -f1)")
  done
  uniq_count="$(printf '%s\n' "${hashes[@]}" | sort -u | wc -l | tr -d ' ')"
  if (( uniq_count > 1 )); then
    echo "PASS — 采样 ${#hashes[@]} 个时刻（${PROBE_TIMES[*]}），出现 ${uniq_count} 种画面：?t= 生效"
    exit 0
  fi
  echo "FAIL — ${#hashes[@]} 个时刻（${PROBE_TIMES[*]}）画面完全相同：页面不随 t 变化" >&2
  echo "  若是刻意静止的开场（标题卡等），用 ./scripts/shot.sh --probe <html> <t1> <t2> 指定时间点，" >&2
  echo "  或在出片时加 render_mp4.sh 的 --allow-static。" >&2
  echo "  否则检查：页面是否实现了 ?t=；draw(t) 是否真的读 t。" >&2
  exit 1
fi

if [[ "$verify" -eq 1 ]]; then
  tmp1="$(mktemp "${TMPDIR:-/tmp}/anim-v1-XXXXXX.png")"
  tmp2="$(mktemp "${TMPDIR:-/tmp}/anim-v2-XXXXXX.png")"
  trap 'rm -f "$tmp1" "$tmp2"' EXIT
  shoot "$tmp1" || exit 1
  shoot "$tmp2" || exit 1
  h1="$(shasum "$tmp1" | cut -d' ' -f1)"
  h2="$(shasum "$tmp2" | cut -d' ' -f1)"
  if [[ "$h1" == "$h2" ]]; then
    echo "PASS — t=$at 两次截图一致（${h1}）"
    exit 0
  fi
  echo "FAIL — t=$at 两次截图不一致：画面存在隐藏状态或随机源" >&2
  echo "  $h1" >&2
  echo "  $h2" >&2
  echo "改法见 references/RENDER.md §9：随机改用种子生成器，状态提到启动期。" >&2
  exit 1
fi

shoot "$out" || exit 1
echo "$out"
