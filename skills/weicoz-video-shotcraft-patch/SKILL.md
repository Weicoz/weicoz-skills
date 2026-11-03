---
name: weicoz-video-shotcraft-patch
version: 1.5.0
description: 做解说片、讲解视频或产品宣传片的总入口：用户只点本 skill 即可，本 skill 会自行加载 video-shotcraft（镜头与画面流程）和 weicoz-zero-tts（配音、字级对齐）。补 video-shotcraft 缺的环节：旁白当时钟的解说片顺序、字幕与安全区、色系连续、配音语速校准（主力 weicoz-zero-tts，兜底 edge-tts）、中文数字配音稿与多音字检查、选声线与识别回读、词级时间、真实素材选材与来源登记、声画同步与确定性检查、只重渲改动镜头、独立审查循环、过程卫生。 Compensation add-on for video-shotcraft full films: captions and safe zone, palette continuity, voice-speed calibration, sync and determinism checks, partial re-render, fresh-reviewer loop.
---

# video-shotcraft 补偿包

补 video-shotcraft 的缺口，不复制它的流程。主流程以 `video-shotcraft` 为准；本 skill 只追加下面几步。脚本路径相对本 skill 目录，`<工程>` 是 Remotion 工程根目录。

## 入口：只点本 skill，另外两个由本 skill 加载

用户做视频时只需调用本 skill，不必再点另外两个。开始时依次加载：

1. **`video-shotcraft`**：开工即加载，用它的模式选择、镜头卡、分镜、终检流程；本 skill 的各步插在它的流程里。
2. **`weicoz-zero-tts`**：有旁白时，在选声线、合成之前加载，用它的音色库、试听页、排队规则。本 skill 的 `calibrate-voice.py`、`voice-consistency.py`、`align-words.py` 都调用它的 `zero_tts.py`。

按宿主的方式调用（Claude Code 用 Skill 工具，Codex 用 `$name`）。调用被拒或找不到时，按全局规则读该 skill 的原文 `SKILL.md` 执行，不判定为未安装。两者已在本轮加载过就不重复加载。

## 0. 解说片：旁白是时钟
video-shotcraft 面向产品宣传片，时间线跟 BGM 节拍走。有旁白的解说片改用旁白当时钟，顺序固定：定稿 → 合成整片旁白（`calibrate-voice.py`，得到句界）→ 字级时间与识别回读（`align-words.py`，回读差异处理完才往下走）→ 按字级锚点写镜头节拍（`cueN@词`，帧号用 `align-words.py --find` 查）→ `check-sync.py` 核对 → 逐帧渲染后合入旁白。稿子或声线改了，从合成重来，`align-words.py` 必须重跑，时间按新旁白重排。video-shotcraft 核心理念 1–2（真实页面截图、从产品设计系统取 tokens）在有产品页面时照做；讲概念、讲模式的片子没有产品页面，视觉 tokens 在 `design-spec.md` 自定，并写明来源。细则见 [references/voice.md](references/voice.md)。

## 1. 简报前：补四个问题
读 [references/brief-addendum.md](references/brief-addendum.md)，把四项并入产品简报的 1–3 个提问：字幕是否烧录、字幕安全区、色系是否允许中途切换、配音语速目标。完成判据：四项在 `design-spec.md` 里各有明确值。

## 2. 有旁白时：配音校准
读 [references/voice.md](references/voice.md)。换配音后的时间线重排也在那里（`remap-timeline.py`、`make-captions.py`）。

```bash
python3 scripts/calibrate-voice.py <工程> --target <字/分钟> --voice <音色>  # 校准并写入旁白、句界、清单；设置了 ZERO_TTS_API_URL 时用 weicoz-zero-tts
python3 scripts/calibrate-voice.py <工程> --target <字/分钟> --dry-run      # 只试，不动工程
python3 scripts/calibrate-voice.py <工程> --target <字/分钟> --engine edge  # 兜底：weicoz-zero-tts 服务不可用时
python3 scripts/zh-numerals.py <工程>       # 字幕稿(vo/script-display，阿拉伯数字) → 配音稿(vo/script，中文数字)
python3 scripts/check-polyphones.py <工程>  # 多音字与易读错的词；高风险未处理时退出码 1
python3 scripts/align-words.py <工程> [--segs seg01,seg03] [--accept]  # 字级时间 + 识别回读（远端；有差异退出码 1）
python3 scripts/voice-consistency.py <工程> --voice <音色> [--fix]  # 逐句音高/音色漂移（weicoz-zero-tts；在远端计算，本机不装 numpy）
```
配音稿与字幕稿分开：`vo/script-display/` 写阿拉伯数字，是文案唯一来源；`vo/script/` 由 `zh-numerals.py` 生成，读音有歧义的词在 `vo/pronounce.json` 里映射。字幕由 `make-captions.py` 按句序号取字幕稿。校准前必须跑这两个脚本并看输出。
选声线、合成后的识别回读、词级时间也在 voice.md：声线可以由代理按客观指标初筛，用户听过再定；合成后把旁白识别回文字与配音稿逐字比对；句内节拍引用 `vo/cues-words/` 的词级时间。
完成判据：`check-polyphones.py` 高风险为 0、需核对项已看过；`voice-consistency.py` 没有偏离句（weicoz-zero-tts）；识别回读只剩识别误差；实测字/分钟在容差内（edge ±2，weicoz-zero-tts ±5）；`vo/cues/segNN.json` 与 `src/vo-manifest.ts` 已生成；`align-words.py` 已生成 `vo/cues-words/segNN.json`，回读差异逐条听过（无差异或已 `--accept`）；`src/timing.ts` 按实测重排；`design-spec.md` 里的时长只写「见 timing.ts」。

## 2b. 用真实素材时：搜索、挑选、登记
读 [references/media.md](references/media.md)。分镜标出需要真实图片或视频的镜头后，从 Pexels、Pixabay、Unsplash、Wikimedia Commons 选材，合适度与质量优先；下载时登记来源与许可，素材文件不入库、靠来源清单复原。

```bash
python3 scripts/media-source.py search <工程> --q "<英文关键词>" --kind photo|video --shot <镜头>   # 候选与候选页
python3 scripts/media-source.py get <工程> <来源:编号> [--kind video] --shot <镜头> --picked-by "user|agent:理由"   # 下载、转码、登记（视频加 --kind video）
python3 scripts/media-source.py fetch <工程>     # 克隆后按来源清单复原
python3 scripts/media-source.py credits <工程>   # 署名清单与简介署名文字
python3 scripts/check-media.py <工程>            # 来源、许可、规格、署名、盗链检查
```
完成判据：`check-media.py` 无错误；需要署名的素材都在 `media/CREDITS.md`。

## 3. 派镜头实现
读 [references/delegation.md](references/delegation.md) 套派单模板，完成判据以该文件为准：`check-shots.py` 无错误、`check-sync.py` 无红色、带字幕条的合成静帧已看。

```bash
python3 scripts/check-shots.py <工程>   # 类型检查是否真能跑、字号、非确定 API、字幕属性、色板
python3 scripts/check-sync.py <工程>    # 节拍帧与字级锚点（cueN@词）或句窗口的偏差
python3 scripts/align-words.py <工程> --find segNN 词   # 查词在镜头内的帧号
```

## 4. 修复轮次：只渲改动镜头
```bash
python3 scripts/render-shots.py <工程> --base <旧整片.mp4> --out <新整片.mp4> --ids s7,s8 --props '<与旧片相同的 props>'
```
镜头总帧数没变时才能用；变了就全片重渲。先验后渲的顺序见 [references/process-hygiene.md](references/process-hygiene.md)。完成判据：输出帧数等于 `timing.ts` 合计。

## 5. 交付前：独立审查循环
读 [references/review-loop.md](references/review-loop.md)。每轮派全新审查员，FAIL 就修、重渲、再派新审查员，直到结论 PASS（无高、无中）。

```bash
python3 scripts/extract-review-frames.py <工程> <成片.mp4> <证据目录>     # 联系表 + 每句旁白帧号
python3 scripts/check-caption-overlap.py <工程> --plain <无字幕画面.mp4>   # 字幕遮挡扫描
```
完成判据：最后一轮报告结论是 PASS；轮次与遗留低项写进交付说明；每轮都有完整报告（在回复里，或在约定路径的文件里）。

## 6. 全程：过程卫生
读 [references/process-hygiene.md](references/process-hygiene.md)：凭据不进输出、等完成通知、依赖真装好、先验后渲。完成判据：会话输出里没有环境变量或进程参数；渲染都已收到完成通知。
