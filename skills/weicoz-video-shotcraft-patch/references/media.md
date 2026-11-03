# 真实素材：搜索、挑选、登记

镜头需要真实照片或视频时，从公开素材库取，不从搜索引擎随手拿图。每条素材下载时登记来源与许可，成片交付时自动生成署名。选材以「合适」和「质量」优先，是否需要署名是次要考虑。

## 来源与许可

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
- 平台许可管不到肖像权和商标权：画面里能认出的人脸、品牌标志，商业片避开或打码。

## 流程

1. **简报**：问清用不用真实素材、只用哪些来源，写进 `design-spec.md` 的「素材」一行（见 [brief-addendum.md](brief-addendum.md)）。
2. **分镜**：分镜表加「素材」列，每镜写「手搭 / 真实图片 / 真实视频」和关键词（英文关键词在素材库里命中率更高）。
3. **搜索**（与配音并行）：
   ```bash
   python3 scripts/media-source.py search <工程> --q "water delivery station" --kind video --shot s4 --min-dur 6
   ```
   结果按质量与合适度排序（分辨率、画幅接近 16:9、视频时长够不够、来源相关度），低于 1920 宽的默认过滤；默认只要横图（成片 16:9），确实要竖图或方图时加 `--orientation portrait|square|any`。同时生成候选页 `media/candidates/<shot>.html`：缩略图、来源、许可、作者、分辨率、时长、分数，每张卡可复制下载命令。缺 Key 的来源会跳过并提示怎么配。
4. **挑选**：共同创作由用户在候选页挑；自主创作由代理挑分数最高、且画面内容与该句旁白对得上的一条，`--picked-by` 写明理由。
5. **下载与登记**（字级时间出来之后做，这时才知道每个镜头准确要多长）：
   ```bash
   python3 scripts/media-source.py get <工程> pexels:123456 --kind video --shot s4 --picked-by "agent:画面是送水站门口，与 cue2 对得上"
   ```
   视频必须加 `--kind video`（Pexels、Pixabay 的照片与视频编号会重号；候选页复制出的命令已带上）。视频转成 H.264、恒定帧率（默认 30）、最长边不超过 1920×1080，默认去掉音轨；文件放 `public/media/<shot>/`，登记到 `media/sources.json`。视频时长要不短于镜头里它出现的时长，不够就换一条或改分镜，不循环播放凑数。
6. **实现**：真实视频用 video-shotcraft 的 `ClipCard` 放进镜头，图片用 `Img` + `staticFile('media/...')`。出现时机照样写字级锚点 `cueN@词`（见 [delegation.md](delegation.md)）。不得直接引用网络地址。
7. **检查**：`python3 scripts/check-media.py <工程>`，无错误才能渲染。
8. **交付**：`python3 scripts/media-source.py credits <工程>` 生成 `media/CREDITS.md`，末尾是可贴进视频简介的署名文字；需要署名的素材（CC BY、CC BY-SA、Unsplash）必须出现在里面。

## 入库与复原

- `media/sources.json`、`media/CREDITS.md` 入库；`public/media/` 下的素材文件不入库，`media/candidates/` 也不入库。
- 克隆后或文件丢失时：`python3 scripts/media-source.py fetch <工程>` 按来源清单重新下载，用 `src_sha256` 校验原始文件没变，再用同样的参数转码。原始文件变了（来源方替换或下架）会报错，此时重新挑选。

## 完成判据

`check-media.py` 无错误；每条素材在 `media/sources.json` 有来源、作者、许可、哈希和挑选理由；需要署名的素材都在 `media/CREDITS.md` 里；审查员按 [review-loop.md](review-loop.md) 的 P5 看过人脸、商标与相关性。
