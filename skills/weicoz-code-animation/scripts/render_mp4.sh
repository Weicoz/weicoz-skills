#!/usr/bin/env bash
# 把支持 ?t= 定格的单文件 html 逐帧截成 mp4。
#
# 用法：
#   ./scripts/render_mp4.sh <html> <输出 mp4> <时长秒> [fps=30] [宽=1920] [高=1080] [并行=6] [--audio 音频] [--allow-static]
# 例（<你的产物>.html 换成实际路径；库自带样片在 references/examples/自测样片_A1字雨/）：
#   ./scripts/render_mp4.sh <你的产物>.html out.mp4 12 30 1920 1080 6
#   ./scripts/render_mp4.sh <你的产物>.html out.mp4 12 --audio bgm.mp3
#   ./scripts/render_mp4.sh card.html out.mp4 2 --allow-static      # 刻意做的静态/标题卡成片
#   ./scripts/render_mp4.sh <你的产物>.html out.mp4 8 --probe-times "1.5 2.5"  # 自定义探测时刻
#
# 原理：每一帧用 Chrome headless 打开 "<html>?t=<秒>" 截一张 PNG，再用 ffmpeg 合成。
# 前提：页面支持 ?t=<秒> 定格渲染（输出契约见 references/RENDER.md）；出片前会先 probe，不通过就拒绝。
set -euo pipefail

if [[ $# -lt 3 ]]; then
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi

html="$1"; out="$2"; dur="$3"; shift 3

fps=30; w=1920; h=1080; par=6; audio=""; allow_static=0; probe_times=""
positional=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --audio)
      [[ -n "${2:-}" ]] || { echo "--audio 缺少文件路径" >&2; exit 2; }
      audio="$2"; shift 2 ;;
    --allow-static) allow_static=1; shift ;;
    --probe-times)
      [[ -n "${2:-}" ]] || { echo "--probe-times 缺少时间点，例如 \"0.5 1.5 2.5\"" >&2; exit 2; }
      probe_times="$2"; shift 2 ;;
    *) positional+=("$1"); shift ;;
  esac
done
[[ ${#positional[@]} -gt 0 ]] && fps="${positional[0]}"
[[ ${#positional[@]} -gt 1 ]] && w="${positional[1]}"
[[ ${#positional[@]} -gt 2 ]] && h="${positional[2]}"
[[ ${#positional[@]} -gt 3 ]] && par="${positional[3]}"

[[ -f "$html" ]] || { echo "找不到页面：$html" >&2; exit 1; }
[[ "$dur" =~ ^[0-9]+(\.[0-9]+)?$ ]] && python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) > 0 else 1)" "$dur" \
  || { echo "时长必须是正的秒数：$dur" >&2; exit 1; }
[[ "$fps" =~ ^[0-9]+$ ]] && (( fps >= 1 )) || { echo "fps 必须是 ≥1 的整数：$fps" >&2; exit 1; }
[[ "$par" =~ ^[0-9]+$ ]] && (( par >= 1 )) || { echo "并行数必须是 ≥1 的整数：$par" >&2; exit 1; }
[[ "$w" =~ ^[0-9]+$ ]] && (( w >= 16 )) || { echo "宽度必须是整数像素：$w" >&2; exit 1; }
[[ "$h" =~ ^[0-9]+$ ]] && (( h >= 16 )) || { echo "高度必须是整数像素：$h" >&2; exit 1; }

ff="${FFMPEG_BIN:-ffmpeg}"
fp="${FFPROBE_BIN:-ffprobe}"
command -v "$ff" >/dev/null || {
  echo "错误：未找到 ffmpeg。请安装，或指定路径：export FFMPEG_BIN=/path/to/ffmpeg" >&2
  exit 1
}
if [[ -n "$audio" ]]; then
  [[ -f "$audio" ]] || { echo "找不到音频：$audio" >&2; exit 1; }
  if command -v "$fp" >/dev/null; then
    adur="$("$fp" -v error -show_entries format=duration -of csv=p=0 "$audio" 2>/dev/null || true)"
    if [[ -n "$adur" ]]; then
      python3 - "$adur" "$dur" <<'PY' || true
import sys
a, d = float(sys.argv[1]), float(sys.argv[2])
if a < d - 0.05:
    print(f"提示：音频 {a:.2f}s 短于视频 {d:.2f}s，尾部会补静音。", file=sys.stderr)
elif a > d + 0.05:
    print(f"提示：音频 {a:.2f}s 长于视频 {d:.2f}s，会被裁到 {d:.2f}s。", file=sys.stderr)
PY
    fi
  fi
fi

here="$(cd "$(dirname "$0")" && pwd)"

# 出片前先验 ?t=：多点采样若画面全同，说明页面不随 t 变化，出来只会是静帧视频。
if (( allow_static == 0 )); then
  probe_args=(--probe "$html")
  if [[ -n "$probe_times" ]]; then
    # shellcheck disable=SC2206
    probe_args+=($probe_times)
  fi
  if ! "$here/shot.sh" "${probe_args[@]}" >/dev/null; then
    echo "错误：页面似乎不随 t 变化（probe 未通过），已停止出片。" >&2
    echo "  先单独跑：./scripts/shot.sh --probe \"$html\"" >&2
    echo "  若是刻意做的静态/标题卡成片，加 --allow-static。" >&2
    exit 1
  fi
fi

frames=$(python3 -c "import math,sys; print(max(1, math.ceil(float(sys.argv[1]) * int(sys.argv[2]) - 1e-9)))" "$dur" "$fps")
tmp="$(mktemp -d "${TMPDIR:-/tmp}/anim-render-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

echo "渲染 ${frames} 帧（${dur}s @ ${fps}fps，${w}x${h}，并行 ${par}）→ $tmp"
if (( frames > 3000 )); then
  echo "提示：${frames} 帧较多，逐帧启动浏览器会花较长时间（约 $(( frames / 25 )) 分钟）。" >&2
fi

# 逐帧截图：每帧独立 Chrome 进程，故并行安全。t 用 6 位小数，避免 t 精度不足导致相邻帧相同。
seq 0 $((frames - 1)) | xargs -P "$par" -I{} bash -c '
  i="$1"; fps="$2"; html="$3"; tmp="$4"; w="$5"; h="$6"; shot="$7"
  at=$(python3 -c "import sys; print(f\"{int(sys.argv[1]) / int(sys.argv[2]):.6f}\")" "$i" "$fps")
  "$shot" "$html" "$at" "$(printf "%s/f_%05d.png" "$tmp" "$i")" "$w" "$h" >/dev/null
' _ {} "$fps" "$html" "$tmp" "$w" "$h" "$here/shot.sh"

made=$(find "$tmp" -name 'f_*.png' | wc -l | tr -d ' ')
if [[ "$made" -ne "$frames" ]]; then
  echo "错误：只截到 $made/$frames 帧，已停止出片。可降低并行数重试。" >&2
  exit 1
fi

# 帧比对：统计全片重复帧。probe 已确认页面随 t 变化，这里再兜一层"渲染链路出问题"。
dup_report="$(shasum "$tmp"/f_*.png | cut -d' ' -f1 | sort | uniq -c | awk '$1>1 {n+=$1-1} END {print n+0}')"
uniq_report="$(shasum "$tmp"/f_*.png | cut -d' ' -f1 | sort -u | wc -l | tr -d ' ')"
if [[ "$uniq_report" -eq 1 ]]; then
  # 走到这里说明 probe 已通过（或显式 --allow-static）：全同更可能是刻意的静态段落，故只警告。
  echo "警告：${frames} 帧画面完全相同，成片是静帧视频。" >&2
  echo "  若这不是你要的，先跑 ./scripts/shot.sh --probe \"$html\" 看 ?t= 是否生效。" >&2
elif [[ "$dup_report" -gt 0 ]]; then
  pct=$(python3 -c "print(f\"{100*$dup_report/$frames:.0f}\")")
  echo "警告：${frames} 帧里有 ${dup_report} 帧与前帧重复（约 ${pct}%）。" >&2
  echo "  常见原因：动作太快且间隔 <1 帧、或 t 精度不足。必要时提高 fps 或改慢动作。" >&2
fi

encode=(-y -framerate "$fps" -i "$tmp/f_%05d.png")
if [[ -n "$audio" ]]; then
  # 规范：AAC 48kHz 立体声，−14 LUFS，真峰 ≤ −1 dBTP；音频短则补静音，不用 -shortest 截断画面。
  # 单遍 loudnorm 只能到 ±2 LU，这里先测一遍再按测量值做第二遍（linear），才能真落在 −14。
  filter="apad=whole_dur=${dur}"
  measured=""
  if command -v "$fp" >/dev/null; then
    report="$("$ff" -hide_banner -nostats -i "$audio" -af "${filter},loudnorm=I=-14:TP=-1:LRA=11:print_format=json" -f null - 2>&1 || true)"
    measured="$(printf '%s' "$report" | python3 -c '
import json, re, sys
text = sys.stdin.read()
m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", text, re.S)
if not m:
    sys.exit(0)
try:
    d = json.loads(m.group(0))
    vals = [d["input_i"], d["input_tp"], d["input_lra"], d["input_thresh"], d["target_offset"]]
except (KeyError, json.JSONDecodeError):
    sys.exit(0)
if any(v in ("-inf", "inf", "nan") for v in vals):
    sys.exit(0)
print(":".join(vals))
' || true)"
  fi
  if [[ -n "$measured" ]]; then
    IFS=: read -r m_i m_tp m_lra m_thresh m_off <<<"$measured"
    afilter="${filter},loudnorm=I=-14:TP=-1:LRA=11:measured_I=${m_i}:measured_TP=${m_tp}:measured_LRA=${m_lra}:measured_thresh=${m_thresh}:offset=${m_off}:linear=true"
  else
    afilter="${filter},loudnorm=I=-14:TP=-1:LRA=11"
  fi
  encode+=(-i "$audio" -c:a aac -b:a 192k -ar 48000 -ac 2 -af "$afilter")
fi
mkdir -p "$(dirname "$out")"
"$ff" -loglevel error "${encode[@]}" \
  -t "$dur" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \
  "$out"

echo "完成：$out"
if command -v "$fp" >/dev/null; then
  "$fp" -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate,channels \
    -of default=noprint_wrappers=1 "$out" 2>/dev/null | sed 's/^/  /'
fi
