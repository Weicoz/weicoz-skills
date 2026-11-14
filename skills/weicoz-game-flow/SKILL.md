---
name: weicoz-game-flow
version: 1.4.0
description: 小游戏开发总流程（Cocos Creator 3.8 + 微信小游戏）：开项目、先找乐趣再工程化的两段式路线、阶段门与各阶段该用的 skill。用于开始或接手一个小游戏项目、问“下一步做什么”、判断能否进入下一阶段。
---

# 小游戏开发流程

一句话：**先让人玩上，再写规格**。乐趣没被用户亲手确认前，不写 spec 和票据。

本套件其余 skill 可能被宿主设为只能手动调用。调用被拒时，直接读它的 `SKILL.md`：与本文件同级的 `../<skill 名>/SKILL.md`；用了 skill 分层工具时在 `~/.agents/skill-tiers/library/<skill 名>/SKILL.md`。

## 人工检查点

制作人只在下面 4 个节点介入。节点之间你自主推进，不打断制作人；拿不准但可逆的技术选择自己定，写进 `docs/PENDING.md` 的“待制作人确认”，到下一个节点一起问。只有阻塞且没有替代路径时才单独提问（例如所有验证路径都不可用）。

| 节点 | 时机 | 制作人做什么 | 你准备什么 |
| --- | --- | --- | --- |
| H0 环境 | 每台机器/账号一次 | 微信开发者工具登录并开服务端口；申请小游戏测试号，把 AppID 写进 `WECHAT_APPID` | 预检结果里所有“用户 …”项，一条消息列全 |
| H1 立项 | 每个项目一次 | 回答立项问题：参考、平台、差异化、非目标 | 设计简报草稿 + 编号选择题 |
| H2 灰盒门 | 阶段 1 结束 | 手机玩 3 分钟，给方向结论；顺带答积压的待定项 | 验收包（`references/acceptance-pack.md`） |
| H3 竖切门 | 阶段 3 结束 | 真机试玩；选美术方向；答积压的待定项 | 验收包 |

上线（类目资质、备案、提审）也由制作人操作，按 `weicoz-cocos-dev` 的 `references/wechat-platform.md` 清单一次性准备材料。

验收包发出前，必须先把能自动验证的全部跑完；不得把“帮我看看能不能打开”这类可自动验证的事交给制作人。

## 套件分工

| skill | 管什么 |
| --- | --- |
| `weicoz-game-flow`（本文件） | 阶段、阶段门、衔接 |
| `weicoz-game-design` | 玩法拆解、参考对标、关卡与生成器、数值、IP 安全 |
| `weicoz-cocos-dev` | 代码架构、规则核与视图分层、Cocos 3.8 坑点、类型检查 |
| `weicoz-cocos-run` | 预检、构建、给用户预览、自动试玩、验证分级 |
| `weicoz-game-assets` | 美术方向、素材生成与导入、素材审查 |
| 工程内 `funplay-cocos-mcp-workflow` / `funplay-cocos-ui-composition` | 编辑器内的场景、节点、Prefab、资源、UI 操作（由 funplay-cocos-mcp 安装） |

套件外依赖。没有时按降级做法执行，不因缺 skill 停下：

| 用到的 | 用途 | 没有时 |
| --- | --- | --- |
| `prototype` | 一次性验证玩法 | 在 `spikes/` 下写一次性脚本或网页，结论写进 `docs/PENDING.md` 后删掉 |
| `grill-with-docs` / `grilling` | 逐项追问待定项 | 按 `docs/PENDING.md` 逐条问用户，答案写进 `GLOSSARY.md` 与 `docs/adr/` |
| `to-spec` / `to-tickets` | 规格与票据 | 写 `docs/spec.md`，每票一节：目标、改动范围、验收（对应试玩脚本步骤） |
| `implement` / `implement-spec` / `tdd` | 按票实现 | 逐票实现；规则核先写失败测试再实现 |
| `weicoz-code-review` | 改动审查 | 自审 diff：规则核是否有测试、视图层是否重复判胜负、平台调用是否只在 `platform/` |
| `retro` | 复盘 | 在 `docs/retro.md` 记三项：有用的、卡住的、下次改的 |
| `playwright-cli` | 浏览器截图与试玩 | 任何能打开页面、执行脚本、截图的浏览器自动化工具 |
| `modlens` | 看不了图的模型读帧 | 用能看图的模型做参考拆解 |
| 出图 skill（如 `gpt-image-2`） | 生成素材 | 让用户提供素材，或保留灰盒占位 |

## 阶段 0：开项目

1. Cocos 工程用 Creator 3.8.x。新项目规则核放 `assets/scripts/core/`；已有项目沿用其结构（如 monorepo 的 `packages/`），约定见 `weicoz-cocos-dev` 的分层。
2. 没有 git 仓库就 `git init`；仓库还没有任何提交时，提醒用户先做首次提交，之后的改动才能回退。
3. 跑 `weicoz-cocos-run` 的预检，按提示补 funplay 配置。编辑器可以由你用命令行打开（预检输出里有命令），funplay 项目 skill 可以由你经编辑器脚本安装（见 `weicoz-cocos-run` 第 1 节）。只有编辑器开着时改了 MCP 配置，才需要用户点 Restart；微信开发者工具的服务端口必须由用户开。用户不在场时先走 CLI 路径。
4. 按 `references/project-agents.md` 模板写项目 `AGENTS.md`，写明 Cocos 工程目录与规则核位置。

完成标准：预检无 ❌；`AGENTS.md` 存在；已记录本项目走 MCP 还是 CLI 路径。预检里的“用户 …”项归入 H0，一条消息发给制作人，然后继续阶段 1，不等回复。

## 阶段 1：找乐趣（灰盒）

目标是最快拿到用户能亲手玩的灰盒。

1. 有参考游戏或视频：先按 `weicoz-game-design` 做**参考拆解与对标指标**，得到可量化目标（密度、数量、长度、节奏等）。
2. 规则核写成纯 TS 并配测试；视图层先用 `Graphics` 和纯色块，不等素材。
3. 玩法本身拿不准时，用 `prototype` 做一次性验证，验证完丢掉。
4. 每轮结束按 `weicoz-cocos-run` 第 3 节把可点开的 URL 交给用户。

**灰盒门**（全部满足才进入阶段 2）：

- 运行验证达到“核心循环已验证”（浏览器即可）。
- 对标指标逐项达标，或差距已列出并经用户接受。没有参考视频时，对标指标改用设计简报里的量化目标（单局时长、首次失败出现在第几关、关卡数），写进 `docs/benchmark.md`。
- 制作人收到 H2 验收包，亲手玩过，并明确说方向对。

用户试玩时少解释，困惑本身就是证据。记下：是否看懂第一个目标、是否找到第一个操作、是否把操作和反馈对上、是否知道为什么失败、是否想再来一局。

用户说“太简单”“不像参考”：回到第 1 步调指标，不进入阶段 2。玩法整体换方向：写一条 ADR，删掉旧玩法代码，从阶段 1 重来。

## 阶段 2：锁定决策

用户确认乐趣后，再用 Matt 流程补齐决策：

- 待定项多：`grill-with-docs`，把术语写进 `GLOSSARY.md`，决定写进 `docs/adr/`。
- 跨多个会话：`to-spec` → `to-tickets`。单个会话做得完：跳过，直接阶段 3。

完成标准：待定项清单为空，或剩余项已标“demo 后再定”。

## 阶段 3：生产（竖切）

1. `implement`（多票用 `implement-spec`）。规则核改动走 `tdd`。
2. 平台能力（存档、分享、广告、隐私）按 `weicoz-cocos-dev` 的 `references/wechat-platform.md` 接入；先接存档，广告在流量主开通前用空实现。
3. 美术、音效按 `weicoz-game-assets` 替换灰盒表现。
4. 改动收尾用 `weicoz-code-review`。
5. 目标平台构建与验证用 `weicoz-cocos-run`，跑它第 4 节的发版回归清单。

**竖切门**：

- 运行验证达到“目标平台已验证”（微信开发者工具或真机）。这一步需要用户开开发者工具的服务端口或拿真机；用户不在场时竖切门判为未通过，汇报写“目标平台未验证”和用户要做的那一步。
- `--release` wechatgame 构建的主包 ≤ 4 MB（以 `cocos-build.mjs` 输出的“主包”行为准）。
- 首个循环的画面、UI、音效都已接入，或已由用户明确同意保留占位。
- 发版回归清单在 debug 构建上全部通过。

## 阶段 4：复盘

阶段门通过或项目暂停时，用 `retro` 记录哪些 skill 帮上忙、哪些步骤卡住。

准备上线时，按 `weicoz-cocos-dev` 的 `references/wechat-platform.md` “上线前检查”整理清单和材料。上传、类目与资质、备案、提审由用户在 MP 后台亲自操作。

## Matt 流程在游戏里的用法

| 适合 | 不适合 |
| --- | --- |
| 规则核、可解性、生成器的 `tdd` | 乐趣未知时就 `grilling` 或 `to-spec`：会把错误前提写死 |
| `GLOSSARY.md` 与 ADR 记录玩法转向 | 用测试判断“好不好玩”“够不够难”：交给对标指标和用户试玩 |
| 乐趣锁定后的 `to-spec` / `to-tickets` | 单会话 demo 也走全套 spec → tickets：流程重于代码 |
