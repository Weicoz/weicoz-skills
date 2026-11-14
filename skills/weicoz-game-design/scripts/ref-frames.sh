#!/usr/bin/env bash
# 参考视频抽帧并拼接总览图，供参考拆解与对标测量使用。
# 用法：ref-frames.sh <视频> <输出目录> [每秒帧数，默认 1]
# 产物：<输出目录>/f001.png …，<输出目录>/contact-1.png …（每张 4×3 共 12 帧，长视频分多张，模型看得清）
# 只依赖 ffmpeg 的图片序列输入，不用 glob，Windows 版 ffmpeg 也能跑。
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "用法：$0 <视频> <输出目录> [每秒帧数]" >&2
  exit 2
fi
command -v ffmpeg >/dev/null || { echo "错误：未找到 ffmpeg。macOS 安装：brew install ffmpeg" >&2; exit 1; }

video="$1"; out="$2"; fps="${3:-1}"
[ -f "$video" ] || { echo "错误：视频不存在：$video" >&2; exit 1; }
mkdir -p "$out"
rm -f "$out"/f[0-9][0-9][0-9].png "$out"/contact*.png  # 重跑时清掉旧帧，免得混进总览

ffmpeg -loglevel error -y -i "$video" -vf "fps=${fps}" "$out/f%03d.png"
count=$(find "$out" -name 'f[0-9][0-9][0-9].png' | wc -l | tr -d ' ')
per=12; pages=$(( (count + per - 1) / per ))
for (( p = 1; p <= pages; p++ )); do
  start=$(( (p - 1) * per + 1 )); n=$(( count - start + 1 )); (( n > per )) && n=$per
  ffmpeg -loglevel error -y -start_number "$start" -i "$out/f%03d.png" -frames:v "$n" \
    -vf "scale=360:-1,tile=4x$(( (n + 3) / 4 )):padding=6:color=white" -frames:v 1 "$out/contact-$p.png"
done

duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")
echo "时长 ${duration}s，抽出 ${count} 帧 → $out/（总览 ${pages} 张：$out/contact-*.png）"
