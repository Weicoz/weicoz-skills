---
name: weicoz-ask
version: 1.0.2
description: 这套开发 skill 的导航：先读当前仓库状态判断所处节点，再说明这一步该用哪个 skill、为什么、下一步去哪。覆盖 Matt 主流程与 weicoz 外挂（实现、审查、验证、体检）、Web 与小游戏两条分支、委派与 worktree。用于用户问“现在该干什么”“下一步用哪个 skill”“这种情况用什么”“这套 skill 怎么用”，或接手一个不熟的项目时。
---

# 问路：现在在哪，下一步用什么

一句话：**先看节点，再选 skill**。本文只做导航；要说某个 skill 具体怎么做、或建议跳过某一步，先读那个 skill 的 `SKILL.md`。

Matt 原版 skill（`grill-with-docs`、`to-spec`、`retro` 等）装在 `~/.agents/skills/<名>/`，weicoz 外挂和本文同在一处。skill 调用被拒或找不到时，读 `~/.agents/skill-tiers/library/<名>/SKILL.md` 或 `~/.agents/skills/<名>/SKILL.md` 照做，不得判定没装。

## 1. 先判断节点

在项目目录跑（只读，不改任何文件）：

```bash
node <skill 目录>/scripts/where.mjs [--repo <目录>] [--base <基础分支>]
```

`<skill 目录>` 是本文件所在目录；用了分层工具时是 `~/.agents/skill-tiers/library/weicoz-ask`。

脚本看 git 状态、AGENTS.md 的“## 验证约定”、`tests/e2e`、功能地图、`.scratch` 里未关闭的票据，判断下表除“只有想法”外的 6 个节点之一，并列出下一步。基础分支默认按 develop → main → master 找；项目集成分支不同就传 `--base`。

| 节点 | 怎么判断 | 下一步 |
| --- | --- | --- |
| 只有想法 | 还没有项目目录（脚本无从判断） | 先 `grill-me` 把想法问清楚；决定要做再建目录，转到“未建仓” |
| 未建仓 | 不是 git 仓库 | `git init` 并首次提交；小游戏走 `weicoz-game-flow` 阶段 0；其他项目跑 `setup-matt-pocock-skills` |
| 验证未接入 | AGENTS.md 没有“## 验证约定” | 按 `weicoz-verify` 第 1 节写约定（小游戏用 `weicoz-game-flow` 的模板），让用户确认快检、全检命令 |
| 实现中 | 工作区有未提交改动 | 按 `weicoz-implement-verified` 继续：每轮快检 → `weicoz-code-review` → 全检 → 提交 |
| 待合并 | 分支领先基础分支，工作区干净 | 全检带 `--base`；`weicoz-code-review <基础分支>..HEAD`；`pr` |
| 待实现 | 有未关闭票据 | `weicoz-implement-verified`（单票或整份规格） |
| 空闲 | 以上都不是 | 看第 2 节：新想法、修 bug、体检、复盘 |

脚本只看文件状态，猜不到意图。用户说的事和节点不符时，以用户为准；把脚本输出和你的判断一起告诉用户。

## 2. 主线：想法 → 交付

Matt 的主流程照用，只在实现、审查、验证三处换成 weicoz 的外挂。外挂读 Matt 原文执行，不改原文。

1. **想清楚**：`grill-with-docs`（有仓库时；会写 `GLOSSARY.md` 和 ADR）。没有仓库用 `grill-me`。
2. **纸上定不了的问题**：`prototype` 写一次性代码回答；跨目录时用 `handoff` 来回传。
3. **规模判断**：
   - 一个会话做得完：直接进第 4 步。
   - 多会话：`to-spec` → `to-tickets`（票据带阻塞关系）。1 到 3 步留在同一个上下文里，`to-tickets` 之后再清。
4. **实现**：`weicoz-implement-verified`，代替 `implement`。
   - 单票：每票 `/clear` 后开新上下文。
   - 整份规格：同一 skill 的“整份规格”小节，代替 `implement-spec`；全部票合进集成分支后跑全检。
   - 写代码按 `tdd` 红绿循环；缺陷票先写能复现的失败测试。
5. **审查**：`weicoz-code-review`，代替 `code-review`。提交前审，范围含未提交和未跟踪文件；规范和高风险目录从基础分支读。
6. **验证**：`weicoz-verify`。收尾必跑全检，带 `--base <基础分支>`；只认最后一行“结论：通过”。
7. **交付**：`pr` 写 PR 描述；合并、推送按项目规则和用户授权做。
8. **收尾**：`retro` 往环境里加规则和检查；隔一段时间用 `weicoz-govern` 体检，清掉失效的文档、测试和 worktree。

## 3. 入口：不是从想法开始时

| 情况 | 用什么 | 之后 |
| --- | --- | --- |
| 有 bug、难复现、性能回退 | `diagnosing-bugs` | 修好后加回归测试，跑全检；同一会话里 `retro` |
| 积压的外来 issue | `triage` | 产出的票交给 `weicoz-implement-verified`；`to-tickets` 出的票不用再 triage |
| 大到一个会话装不下的新项目或大功能 | `wayfinder` | 地图清楚后回到 `to-spec` |
| 要先查资料 | `research` | 结果带进 `grill-with-docs` |
| 卡在别人的信息上 | `to-questionnaire` | 回收的答案带进 `grill-with-docs` 或 `to-spec` |
| 只有人能做的步骤（凭据、控制台、迁移） | `wizard` | 生成脚本交给用户跑 |
| 代码库越改越难改 | `improve-codebase-architecture`，设计用 `codebase-design` | 选中的改进当新想法走主线 |
| 词不清、一个词多种意思 | `domain-modeling` | 写进 `GLOSSARY.md` 或 ADR |

## 4. 按项目类型分支

| 项目 | 总控 | 验证适配器 | 端到端流程怎么写 |
| --- | --- | --- | --- |
| 小游戏（Cocos 3.8 / 微信小游戏） | `weicoz-game-flow`：阶段 0 到 3、人工检查点 H0 到 H3。设计用 `weicoz-game-design`，代码用 `weicoz-cocos-dev`，素材用 `weicoz-game-assets` | `weicoz-cocos-run` 的 `cocos-verify.mjs` | 测试钩子 + 试玩脚本，见 `weicoz-cocos-run` 的 `references/playtest-hook.md` |
| Web | 第 2 节主线 | `weicoz-verify` 的 `web-verify.mjs`（`references/adapter-web.md`） | `weicoz-verify` 的 `references/e2e-authoring.md` |
| 其他 | 第 2 节主线 | 自建一条命令，骨架见 `weicoz-verify` 的 `references/custom-adapter.md` | 同上，按项目能观测的结果写 |

小游戏项目里，阶段和人工检查点以 `weicoz-game-flow` 为准；本文的节点只说明代码层面走到哪了。

## 5. 验证节点细则

| 问题 | 答案 |
| --- | --- |
| 什么时候跑哪档 | 写代码时跑相关单个测试；每轮写完跑快检；合并、交付前跑全检。三档定义见 `weicoz-verify` 第 3 节 |
| 结论“未验证” | 看括号里缺什么：缺环境就补环境；用了 `--no-checks`、`--script` 这类缩小范围的开关，要去掉开关重跑 |
| 结论“不通过” | 按 `weicoz-verify` 第 4 节修；同一项连续 2 次修不好，或整个任务累计 5 轮不通过，就停下报告 |
| 要新写端到端流程 | `e2e-authoring.md` 第 0 到 8 步；第 5 步“证明能抓错”不得跳过 |
| 改了验证配置或 AGENTS.md | 带 `--base` 时脚本会判“未验证”；把改动列给用户确认 |
| 汇报 | 结论行原文、联系图路径、验证级别；没看图就写“视觉未验证” |

## 6. 谁来做

| 情况 | 用什么 |
| --- | --- |
| 小改动 | 当前会话自己做 |
| 范围明确、改多个文件 | `implementer` 子代理，加 worktree 隔离 |
| 把一张票或整份规格交给外部编码代理 | `weicoz-agent-implement` / `weicoz-agent-implement-spec` |
| 放到别的机器跑（需用户授权） | `weicoz-remote-dispatch` |
| 经 T3 派给 DSH、Kimi 等 harness | `weicoz-t3-dispatch` |
| 建、切、删 worktree | `weicoz-worktrunk`（`wt`），不直接用 `git worktree` |

委派出去的结果要回读验收：执行者自己说的“通过”不算，要看结论行和证据。

## 7. 阶段之间

一个阶段做完（想清楚、写完票、实现完一票），先决定上下文怎么处理，再进下一步：

- 后面还要用现在的上下文：继续。
- 后面用不上：`/clear`。
- 换目录、换 harness 或交给别人：`handoff`。
- 只是个范围小的旁支任务：派子代理，只收摘要。
- 都不是，上下文又快满了：`/compact`。

Matt 的 `ask-matt` 和它的 `PHASE-BOUNDARIES.md` 讲了这几种选择的理由。只问 Matt 原版流程的问题时，直接用 `ask-matt`。

## 8. 回答用户的格式

1. 当前节点和依据：贴 `where.mjs` 的节点行，或说明为什么不用脚本。
2. 下一步：一到三个 skill，写清各自做什么、做完到哪个节点。
3. 用户问的是具体情况：用第 3 到 6 节的表回答，并给出 skill 名。
4. 前置缺什么：例如没有验证约定、没有功能地图，先补。
