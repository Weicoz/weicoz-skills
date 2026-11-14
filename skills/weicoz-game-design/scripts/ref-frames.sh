#!/usr/bin/env bash
# 参考视频抽帧并拼接总览图，供参考拆解与对标测量使用。
# 用法：ref-frames.sh <视频> <输出目录> [每秒帧数，默认 1]
# 产物：<输出目录>/f001.png …，<输出目录>/contact.png（4 列总览图）
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "用法：$0 <视频> <输出目录> [每秒帧数]" >&2
  exit 2
fi
command -v ffmpeg >/dev/null || { echo "错误：未找到 ffmpeg。macOS 安装：brew install ffmpeg" >&2; exit 1; }

video="$1"; out="$2"; fps="${3:-1}"
[ -f "$video" ] || { echo "错误：视频不存在：$video" >&2; exit 1; }
mkdir -p "$out"

ffmpeg -loglevel error -y -i "$video" -vf "fps=${fps}" "$out/f%03d.png"
count=$(find "$out" -name 'f*.png' | wc -l | tr -d ' ')
rows=$(( (count + 3) / 4 ))
ffmpeg -loglevel error -y -pattern_type glob -i "$out/f*.png" \
  -vf "scale=360:-1,tile=4x${rows}:padding=6:color=white" -frames:v 1 "$out/contact.png"

duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")
echo "时长 ${duration}s，抽出 ${count} 帧 → $out/（总览：$out/contact.png）"
