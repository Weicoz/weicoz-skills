# 素材：素材库与 AI 生成

镜头需要照片或视频时，先从公开素材库找，找不到合适的或需要风格化时再用 AI 生成。不从搜索引擎随手拿图。每条素材都登记来源与许可，交付时自动生成署名。选材以「合适」和「质量」优先，是否需要署名是次要考虑。

## 决策顺序

1. **先问要不要素材，并给建议。** 简报或分镜阶段，按镜头列出建议，再问用户：
   - 默认手搭动图：讲概念、数字、流程、对比的镜头。
   - 建议用素材：要让观众看到真实场景、真实事物的镜头（送水站、仓库、街景），写出建议的关键词和类型（图片或视频）。
   - 用户决定哪些镜头要素材，写进 `design-spec.md` 的「素材」一行和分镜表的「素材」列。
2. **要素材的镜头，先找素材库**（下文「素材库」）。
3. **素材库没有合适的，或这一镜需要风格化**（比喻画面、与整片配色统一的插画、现实里拍不到的画面），**再走 AI 生成**（下文「AI 生成」），同样先给建议：建议生成什么、图片还是视频、提示词草稿。
4. **红线（三种素材都适用）**：真实人物、真实品牌、真实事件不用 AI 生成，走素材库或手搭；能认出的人脸、品牌标志，商业片避开或打码。

## 素材库

### 来源与许可

| 来源 | 内容 | 许可 | 环境变量 |
|---|---|---|---|
| Pexels | 照片、视频 | Pexels 许可，可商用，不强制署名 | `PEXELS_API_KEY` |
| Pixabay | 照片、视频 | Pixabay 许可，同上 | `PIXABAY_API_KEY` |
| Unsplash | 照片 | Unsplash 许可，可商用；API 规范要求标注作者 | `UNSPLASH_ACCESS_KEY` |
| Wikimedia Commons | 照片、视频，含真实事件与历史影像 | 逐个文件标注：CC0、公有领域、CC BY、CC BY-SA 等 | 不需要 |

- 默认接受：平台许可（pexels、pixabay、unsplash）、CC0、公有领域、CC BY。
- CC BY-SA 需显式加 `--allow-sa`：它要求衍生作品沿用同一许可，素材放进成片后，整支视频可能都要按 BY-SA 开放。用之前在 `design-spec.md` 写明。
- 一律拒绝：带 NC（禁止商用）、ND（禁止改作）或许可不明的素材。
- 许可以下载时向来源重新查询的详情为准，不信任搜索结果。
- Pixabay 账号没有原图权限时，照片最大只有 1280 宽，会被默认的 `--min-width 1920` 过滤掉；只做小图时可放宽到 1280。Wikimedia 照片宽于 3840 时下载 3840 宽的版本。

### 步骤

1. **搜索**（与配音并行）：
   ```bash
   python3 scripts/media-source.py search <工程> --q "water delivery station" --kind video --shot s4 --min-dur 6
   ```
   英文关键词命中率更高。结果按质量与合适度排序（分辨率、画幅接近 16:9、视频时长够不够、来源相关度），低于 1920 宽的默认过滤；默认只要横图（成片 16:9），确实要竖图或方图时加 `--orientation portrait|square|any`。同时生成候选页 `media/candidates/<shot>.html` 和缩略图联系表 `media/candidates/<shot>_sheet.jpg`（前 12 条，4 列，从左到右、从上到下 = 排名顺序，终端打印每张对应的编号）。缺 Key 的来源会跳过并提示怎么配。
2. **挑选**：共同创作由用户在候选页挑；自主创作由代理挑。代理必须先看联系表（看不全时用 `media-source.py sheet <工程> --name <shot> --top 24` 重出），确认画面内容与该句旁白对得上，再在分数靠前的几条里选；不得只凭标题或分数挑（实测：标题含 delivery man 的视频，画面其实是一辆停着的厢式货车）。`--picked-by` 必须写「联系表第 N 张」加看到的画面内容（`check-media.py` 会校验，例：`agent:联系表第 1 张，普通人抱纸箱、背景天空，对应 cue4「变成半个业务员」`）。都不合适就换关键词，再不行转 AI 生成。
3. **下载与登记**（字级时间出来之后做，这时才知道每个镜头准确要多长）：
   ```bash
   python3 scripts/media-source.py get <工程> pexels:123456 --kind video --shot s4 --picked-by "agent:联系表第 2 张，…"
   ```
   视频必须加 `--kind video`（Pexels、Pixabay 的照片与视频编号会重号；候选页复制出的命令已带上）。视频转成 H.264、恒定帧率（默认 30）、最长边不超过 1920×1080，默认去掉音轨；文件放 `public/media/<shot>/`，登记到 `media/sources.json`。视频时长要不短于镜头里它出现的时长，不够就换一条或改分镜，不循环播放凑数。

## AI 生成

生成途径不固定。每次要生成时先问用户用哪条途径，例如：
- 出图 skill：`gpt-image-2`（提示词按 `weicoz-gptimage2-prompts` 的写法），由代理直接生成；
- 网页工具：即梦、可灵等，由代理给提示词，用户生成后把文件交过来；
- 用户已有的其他生成服务。

步骤：

1. **写提示词建议**：画面主体、构图（16:9 横图）、风格与配色（取自 `design-spec.md`，与相邻镜头一致）、光线、要避免的元素（文字、水印、变形的手）。视频另写镜头运动和时长（不短于它在镜头里出现的时长）；视频建议先生成一张关键帧，确认后再图生视频。
2. **一次出多个候选**（图片 3–4 张，视频 2–3 段），放进一个目录，拼联系表挑选：
   ```bash
   python3 scripts/media-source.py sheet <工程> --name s4-gen --files 候选1.png 候选2.png 候选3.png
   ```
3. **导入并登记**挑中的那个：
   ```bash
   python3 scripts/media-source.py import <工程> 候选2.png --shot s4 --tool "gpt-image-2 skill" --model gpt-image-2 \
     --prompt "完整提示词" --picked-by "agent:联系表第 2 张，…"
   ```
   `--tool`、`--prompt`、`--picked-by` 必填。视频按素材库同一套参数转码。文件存两份：入库副本 `media/generated/<shot>/`（唯一真相源，生成结果无法复现），渲染用副本 `public/media/<shot>/`。
4. **检查生成质量**：出一张含该素材的静帧，看手指与肢体、乱码文字、透视与比例、风格是否与相邻镜头断层。不合格就改提示词重来，不靠后期遮。
5. **AI 标识**：署名清单与视频简介写明「部分画面由 AI 生成」（`credits` 自动加），画面上不加角标。

## 实现、检查、交付（两种素材相同）

- **实现**：视频用 video-shotcraft 的 `ClipCard` 放进镜头，图片用 `Img` + `staticFile('media/...')`。出现时机写字级锚点 `cueN@词`（见 [delegation.md](delegation.md)）。不得直接引用网络地址。
- **检查**：`python3 scripts/check-media.py <工程>`，无错误才能渲染。
- **交付**：`python3 scripts/media-source.py credits <工程>` 生成 `media/CREDITS.md`，末尾是可贴进视频简介的署名文字；需要署名的素材（CC BY、CC BY-SA、Unsplash）和 AI 生成声明都在里面。

## 入库与复原

- 入库：`media/sources.json`、`media/CREDITS.md`、`media/generated/`（AI 生成的素材）。
- 不入库：`public/media/`（渲染用副本）、`media/candidates/`（候选页与联系表）。
- 克隆后或文件丢失时：`python3 scripts/media-source.py fetch <工程>`。素材库条目按来源清单重新下载，用 `src_sha256` 校验原始文件没变再转码（来源方替换或下架会报错，此时重新挑选）；AI 生成条目从 `media/generated/` 复制。

## 完成判据

`check-media.py` 无错误；每条素材在 `media/sources.json` 有来源（素材库）或途径与提示词（AI 生成）、许可、哈希和挑选理由；署名清单包含所有需署名的素材和 AI 生成声明；审查员按 [review-loop.md](review-loop.md) 的 P5 看过人脸、商标、相关性与生成瑕疵。
