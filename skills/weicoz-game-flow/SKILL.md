---
name: weicoz-game-flow
version: 1.1.0
description: 小游戏开发总流程（Cocos Creator 3.8 + 微信小游戏）：开项目、先找乐趣再工程化的两段式路线、阶段门与各阶段该用的 skill。用于开始或接手一个小游戏项目、问“下一步做什么”、判断能否进入下一阶段。
---

# 小游戏开发流程

一句话：**先让人玩上，再写规格**。乐趣没被用户亲手确认前，不写 spec 和票据。

## 套件分工

| skill | 管什么 |
| --- | --- |
| `weicoz-game-flow`（本文件） | 阶段、阶段门、衔接 |
| `weicoz-game-design` | 玩法拆解、参考对标、关卡与生成器、数值、IP 安全 |
| `weicoz-cocos-dev` | 代码架构、规则核与视图分层、Cocos 3.8 坑点、类型检查 |
| `weicoz-cocos-run` | 预检、构建、给用户预览、自动试玩、验证分级 |
| `weicoz-game-assets` | 美术方向、素材生成与导入、素材审查 |
| 工程内 `funplay-cocos-mcp-workflow` / `funplay-cocos-ui-composition` | 编辑器内的场景、节点、Prefab、资源、UI 操作（由 funplay-cocos-mcp 安装） |

## 阶段 0：开项目

1. Cocos 工程用 Creator 3.8.x；规则核放 `assets/scripts/core/`，写成纯 TS（约定见 `weicoz-cocos-dev`）。
2. 没有 git 仓库就 `git init`，并提醒用户做首次提交。
3. 跑 `weicoz-cocos-run` 的预检，按提示装好 funplay 项目 skill。
4. 按 `references/project-agents.md` 模板写项目 `AGENTS.md`。

完成标准：预检无 ❌，`AGENTS.md` 存在。

## 阶段 1：找乐趣（灰盒）

目标是最快拿到用户能亲手玩的灰盒。

1. 有参考游戏或视频：先按 `weicoz-game-design` 做**参考拆解与对标指标**，得到可量化目标（密度、数量、长度、节奏等）。
2. 规则核写成纯 TS 并配测试；视图层先用 `Graphics` 和纯色块，不等素材。
3. 玩法本身拿不准时，用 `prototype` 做一次性验证，验证完丢掉。
4. 每轮结束按 `weicoz-cocos-run` 第 3 节把可点开的 URL 交给用户。

**灰盒门**（全部满足才进入阶段 2）：

- 运行验证达到“核心循环已验证”（浏览器即可）。
- 对标指标逐项达标，或差距已列出并经用户接受。
- 用户亲手玩过，并明确说方向对。

用户试玩时少解释，困惑本身就是证据。记下：是否看懂第一个目标、是否找到第一个操作、是否把操作和反馈对上、是否知道为什么失败、是否想再来一局。

用户说“太简单”“不像参考”：回到第 1 步调指标，不进入阶段 2。玩法整体换方向：写一条 ADR，删掉旧玩法代码，从阶段 1 重来。

## 阶段 2：锁定决策

用户确认乐趣后，再用 Matt 流程补齐决策：

- 待定项多：`grill-with-docs`，把术语写进 `GLOSSARY.md`，决定写进 `docs/adr/`。
- 跨多个会话：`to-spec` → `to-tickets`。单个会话做得完：跳过，直接阶段 3。

完成标准：待定项清单为空，或剩余项已标“demo 后再定”。

## 阶段 3：生产（竖切）

1. `implement`（多票用 `implement-spec`）。规则核改动走 `tdd`。
2. 美术、音效按 `weicoz-game-assets` 替换灰盒表现。
3. 改动收尾用 `weicoz-code-review`。
4. 目标平台构建与验证用 `weicoz-cocos-run`。

**竖切门**：

- 运行验证达到“目标平台已验证”（微信开发者工具或真机）。
- wechatgame 主包 ≤ 4 MB。
- 首个循环的画面、UI、音效都已接入，或已由用户明确同意保留占位。
- 测试钩子与试玩脚本可重跑。

## 阶段 4：复盘

阶段门通过或项目暂停时，用 `retro` 记录哪些 skill 帮上忙、哪些步骤卡住。上传、提审、发布不在本套件范围内，需要用户亲自操作。

## Matt 流程在游戏里的用法

| 适合 | 不适合 |
| --- | --- |
| 规则核、可解性、生成器的 `tdd` | 乐趣未知时就 `grilling` 或 `to-spec`：会把错误前提写死 |
| `GLOSSARY.md` 与 ADR 记录玩法转向 | 用测试判断“好不好玩”“够不够难”：交给对标指标和用户试玩 |
| 乐趣锁定后的 `to-spec` / `to-tickets` | 单会话 demo 也走全套 spec → tickets：流程重于代码 |
