---
name: weicoz-video-shotcraft-patch
version: 1.0.0
description: video-shotcraft 的补偿包。做完整宣传片或讲解片时与 video-shotcraft 同时使用，补它缺的环节：字幕与安全区、色系连续、配音语速校准、确定性检查、只重渲改动镜头、独立审查循环、过程卫生。 Compensation add-on for video-shotcraft full films: captions and safe zone, palette continuity, voice-speed calibration, deterministic checks, partial re-render, fresh-reviewer loop.
---

# video-shotcraft 补偿包

补 video-shotcraft 的缺口，不复制它的流程。主流程以 `video-shotcraft` 为准；本 skill 只追加下面六步。脚本路径相对本 skill 目录，`<工程>` 是 Remotion 工程根目录。

## 1. 简报前：补四个问题
读 [references/brief-addendum.md](references/brief-addendum.md)，把四项并入产品简报的 1–3 个提问：字幕是否烧录、字幕安全区、色系是否允许中途切换、配音语速目标。完成判据：四项在 `design-spec.md` 里各有明确值。

## 2. 有旁白时：配音校准
读 [references/voice.md](references/voice.md)。

```bash
python3 scripts/calibrate-voice.py <工程> --target <字/分钟>            # 校准并写入旁白、句界、清单
python3 scripts/calibrate-voice.py <工程> --target <字/分钟> --dry-run  # 只试，不动工程
```
完成判据：实测字/分钟在目标 ±2 内，`vo/cues/segNN.json` 与 `src/vo-manifest.ts` 已生成，目标与实测写入 spec。

## 3. 派镜头实现
读 [references/delegation.md](references/delegation.md) 套派单模板。完成判据：每个镜头 `python3 scripts/check-shots.py <工程>` 无错误，且带字幕条的合成静帧已看。

## 4. 修复轮次：只渲改动镜头
```bash
python3 scripts/render-shots.py <工程> --base <旧整片.mp4> --out <新整片.mp4> --ids s7,s8 --props '<与旧片相同的 props>'
```
镜头总帧数没变时才能用；变了就全片重渲。完成判据：输出帧数等于 `timing.ts` 合计。

## 5. 交付前：独立审查循环
读 [references/review-loop.md](references/review-loop.md)。每轮派全新审查员，FAIL 就修、重渲、再派新审查员，直到结论 PASS（无高、无中）。

```bash
python3 scripts/extract-review-frames.py <工程> <成片.mp4> <证据目录>     # 联系表 + 每句旁白帧号
python3 scripts/check-caption-overlap.py <工程> --plain <无字幕画面.mp4>   # 字幕遮挡扫描
```
完成判据：最后一轮报告结论是 PASS，轮次与遗留低项写进交付说明。

## 6. 全程：过程卫生
读 [references/process-hygiene.md](references/process-hygiene.md)：不把环境变量或进程参数打进输出，等待渲染用后台通知。凭据一旦打进输出，立刻告诉用户轮换。
