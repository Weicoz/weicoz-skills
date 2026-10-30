---
name: weicoz-code-animation
version: 1.0.0
description: 用 341 种现成风格做代码动画、动效短片或视频。用户要做动画/短片/片头/解说动画/卡点视频/信息图动画/风格化视觉，或说"用某画风（水墨、像素、赛博朋克、某部电影的样子）做一段动画""把这段内容做成视频""做成能放的 mp4"，或提到 canvas 动画、three.js 动画、motion graphic、代码动画、风格库时使用。先本地检索风格库拿到原始提示词，再按固定输出契约出单文件 html 并渲成 mp4。
---

# 代码动画风格库

本地优先。341 种风格、10 个类别、193 张静帧；其中 25 条正文带可直接粘贴的 `S.XX` 参考实现，另有 3 条只有片段（B3、Z5、L20）。全部离线。
无 API、无网络依赖（仅 3D 风格需 CDN 引 three.js）。

风格原文在 `references/library/风格提示词/`，索引在 `references/index.json`（由脚本重建）。

## 三条硬规则

1. **提示词必须读原文**。用 `style_search.py` 定位，再读命中的那一个 `.md` 取「风格提示词」一节。不得凭记忆复述配色、参数、镜头。
2. **产物必须支持 `?t=` 定格**。否则截图核验和逐帧出片都做不了，这是整条流水线的入口。
3. **交付前必须抽帧核验**。没看过画面就说完成，等于没做。

## 工作流

### 第 1 步：选风格

```bash
cd <本 skill 目录>                       # 例如 ~/.agents/skills/weicoz-code-animation

# 不知道选哪类：先看导览
python3 scripts/style_search.py --list-series

# 按内容/画风/情绪检索
python3 scripts/style_search.py 水墨
python3 scripts/style_search.py 数据 新闻 --series L
python3 scripts/style_search.py 粒子 --code          # 只要有可运行实现的
python3 scripts/style_search.py --grep 孤独          # 描述里搜不到时，改搜正文全文
python3 scripts/style_search.py --random 3           # 没主意时随机看三条

# 拿到 ID 后取全文
python3 scripts/style_search.py --id C1 --json       # 输出含 path 字段
```

结果里 `[代码]` 表示正文有可直接粘贴的 `S.XX` 实现；目录里标 `△` 的是片段，要自己补依赖。

然后读 `references/DIRECTORY.md` 决定类别，读命中 `.md` 的「风格提示词」一节。
要专业解说/数据感优先 L 类；要整片结构选 M；要画风选 K/Z/V/R/O；要现成版式选 H。

提示词里出现 `{{ }}` 是要替换的占位内容（主题、时长、标题等），按实际内容填，别原样输出。
命中项的 `.md` 里若还有「导演说明」「成片里的分镜」「补充」，一并读完再动手，镜头顺序就在那里。

### 第 2 步：定参数

读 `references/MIXING.md`。能推断的自己定，只确认会改变成品的三件事：时长、比例、要不要声音。
文案由你写就标注"占位可替换"。

### 第 3 步：出片

读 `references/RENDER.md`，照它的输出契约写**单文件** `index.html`。
产物写到当前工作目录（如 `./demo/`），不要写进本 skill 目录，以免污染库。

- 画布固定 1920×1080（竖屏 1080×1920），CSS 等比缩放居中。
- `draw(t)` 是 t 的纯函数；随机用带种子生成器；`?t=5.7` 定格一帧；空格暂停。
- 中文只用系统字体栈；字号 ≥ 20px；关键文字按 `字数÷4.5+1.5` 秒停留。
- 有参考实现时按 `RENDER.md` §3 接：纯函数式直接调用；A1/B4/D1 三条是增量式，必须用确定性外壳重放。
  依赖按类别不同：只有 A–G 目录下有 `_公共函数.js`，L/Z 没有；L20 的示例依赖库内不存在的 `engine/`。

`demo/index.html` 是占位写法，换成你自己的产物路径；想先跑通流程就用库自带样片
`references/examples/自测样片_A1字雨/index.html`。

```bash
# 0) 先确认 ?t= 真生效（静态页会在这里被拦下）
./scripts/shot.sh --probe demo/index.html

# 抽帧核验（关键动作各截一张）
./scripts/shot.sh demo/index.html 2.0 /tmp/a.png

# 确定性：同一 t 两次必须同哈希（脚本直接判 PASS / FAIL）
./scripts/shot.sh --verify demo/index.html 3.3

# 出片
./scripts/render_mp4.sh demo/index.html out.mp4 8 30 1920 1080 6
```

## 交付前自查

- [ ] 画面与所选风格的配色、笔触、镜头、避免项逐条对得上（不是"大概像"）
- [ ] `?t=` 定格正确（`shot.sh --probe` PASS），同 t 两次哈希一致（`shot.sh --verify` PASS）
- [ ] 文字无超框、无乱码，字号与停留达标
- [ ] mp4 的时长、分辨率、帧率与要求一致；有音轨时脚本已自动做响度归一与 48kHz 立体声
- [ ] 说明里写了风格 ID、参数、音轨情况、文案是否占位

## 文档索引

| 文件 | 内容 |
| --- | --- |
| `references/DIRECTORY.md` | 10 类怎么选 + 8 组常用组合配方 + 反模式 |
| `references/CATALOG.md` | 341 条全量清单（脚本生成，勿手改；用 grep 查，勿整读） |
| `references/RENDER.md` | 输出契约、两套骨架、参考实现接法、核验与出片、失败排查 |
| `references/MIXING.md` | 时长/比例/声音/文字规格/交付清单 |
| `references/index.json` | 结构化索引（脚本生成，勿手改） |
| `references/library/风格挑选.html` | 人工挑选页，双击离线打开，可筛可按类别、可导出清单 |
| `references/library/收录说明.md` | 素材保留/省略清单、更新方法与许可提醒（本 skill 添加） |
| `references/examples/` | 两次实测产物：同一提示词 Opus 与 DeepSeek 的成片源码、一句话出片示例 |

维护库时：新增或修改风格 `.md` 后运行 `python3 scripts/build_index.py` 重建索引，
再用 `python3 scripts/build_index.py --check` 校验。它会核对：正文与挑选页的 ID 是否一致、是否有重复 ID、
挑选页声明的静帧文件是否都还在、以及 name/fit 字段是否漂移（漂移只提示，不阻断）。

## 数据现状

- 341 条中有 8 条是空白占位（M14/15/16/17/26/35/39/40）：无名称、无提示词，检索默认已过滤。
- 可用 333 条；193 条带静帧。
- A–G 的 26 条里有 25 条带可直接粘贴的 `S.XX` 实现（B3 只有片段）；其中 3 条是增量式（A1/B4/D1），要配确定性外壳。
- 另有 3 条片段（B3 粒子聚形、Z5 剪纸、L20 油画厚涂），L10 是 JSON 配置；这些不能直接粘。

## 许可与署名

风格库来源：`references/library/许可与来源.md`（原作者整理，免费使用与传播，**禁止**包装成课程、付费 skill 或任何收费产品出售）。

其中三部分来自开源项目，按 MIT 保留许可与署名：Lemo-Opuscar（L 类、O 类）、mg-styles-15（V 类）、code-video（X 类）。许可原文在 `references/library/第三方许可/`。

本 skill 只做本地检索、出片规范与流水线脚本；不改动、不重写风格提示词原文。

二次分发时分清两块：**原作者整理的非 MIT 内容**（A–G、M/K/Z/H 的中文整理、R、挑选页等）按其约定保持免费、不得收费出售；**来自三个开源项目的 MIT 内容**（L/O 来自 Lemo-Opuscar，V 来自 mg-styles-15，X 来自 code-video）按 MIT 处理，保留版权声明即可，MIT 本身不禁止商用。
