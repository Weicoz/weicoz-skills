---
name: weicoz-cavecrew
description: 派工决策指南——何时派 caveman 风格子代理（investigator 定位代码 / builder 改 1–2 文件 / reviewer 审 diff），而不是主线程自己做或用普通搜索。子代理输出按固定压缩契约回注主上下文，约省 60%。触发：用户说 "$cavecrew"、"cavecrew"、"派 investigator/builder/reviewer"、"用 subagent 干这事"。重建自上游 JuliusBrussee/caveman skills/cavecrew（本机原文缺失，此为忠实还原版）。
---

# Cavecrew 派工决策指南（weicoz 重建版）

> 上游：https://github.com/JuliusBrussee/caveman/tree/main/skills/cavecrew
> 本文件为上游 SKILL.md 的中文忠实还原；上游原文在本机缺失时作为替代。

## 三个子代理

| 子代理 | 职责 | 默认模型 |
|---|---|---|
| `cavecrew-investigator` | 只定位代码：X 在哪个文件哪几行、调用链怎么走 | haiku（可用环境变量覆盖） |
| `cavecrew-builder` | 小改：1–2 个文件的明确修改 | 会话默认 |
| `cavecrew-reviewer` | 审查 diff，逐条给位置+问题+修法 | haiku（可用环境变量覆盖） |

## 何时派 vs 自己做

- 任务 ≤2 文件且路径已知 → **builder**
- 只找不改、"X 在哪/怎么串" → **investigator**
- 有现成 diff 要第二双眼睛 → **reviewer**
- 单文件顺手查一眼 / 改一行 → 不派，主线程直接干（派遣开销 > 收益）
- 大范围重构、跨多文件设计 → 不派，主线程统筹或拆多次派工
- 一场会话里预期 ≥3 次查找/小改 → 值得派，累计省 ~60% 主上下文，防止主上下文耗尽

## 返回契约（子代理输出必须长这样，保证可 grep、可回注）

- **investigator**：path-first、行号跟随、符号一律反引号包裹。
  例：`` `src/auth.ts:42` — `validateToken()` 校验过期时间，被 `refreshFlow()` 调用 ``
- **builder**：简短变更摘要 + 验证令牌（跑了什么检查、结果如何）。
  例：`改了 X → 测试 pass ✅`
- **reviewer**：emoji 标严重度，一行一条：位置、问题、修法。
  例：`🔴 auth.ts:42 无空指针防护 → 加 early return`

## 使用前置条件（本机规则）

1. 派遣前须用户在对话中明确授权（如"用 subagent"）；用户点名 `$cavecrew` 并给出任务即算授权。
2. 本 harness 中对应工具为 `subagent` / `subagent_fork`（未解锁时先推进阶段解锁）。
3. 派工 prompt 里直接内嵌上表职责 + 返回契约，要求输出保持 caveman 压缩风格。
