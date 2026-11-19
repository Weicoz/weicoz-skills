---
name: weicoz-ask
version: 1.0.0
description: weicoz-skills 仓库全部自研 skill 的总导航：按需求找该用哪个 weicoz skill、说明为什么、怎么调用。用于用户问“我的 skill 里有没有能做 X 的”“这件事用我哪个 skill”“我有哪些 skill”“忘了某个 weicoz skill 叫什么”。开发流程下一步问 weicoz-ask-dev；第三方 skill 用 weicoz-skill-tiers 的 find。
---

# weicoz-ask

范围只限 weicoz-skills 仓库（`skills/` 下的自研 skill）。清单不手写：脚本每次现读仓库 README 的“Skill 清单”分组和各 `SKILL.md` 的 frontmatter，新增 skill 后自动可查。

## 1. 先分流

| 用户问的 | 交给 |
| --- | --- |
| 开发项目“现在该干什么”“下一步用哪个 skill” | `weicoz-ask-dev`（读仓库状态判断节点） |
| 小游戏项目的阶段与检查点 | `weicoz-game-flow` |
| 第三方或非 weicoz skill，或要知道分层位置 | `weicoz-skill-tiers` 的 `find <关键词>` |
| 其余：“有没有能做 X 的 weicoz skill”“我有哪些 skill” | 本 skill 第 2 节 |

## 2. 查找

`<skill 目录>` 是本文件所在目录；用了分层工具时是 `~/.agents/skill-tiers/library/weicoz-ask`。

```bash
node <skill 目录>/scripts/ask.mjs                # 按 README 分组列出全部
node <skill 目录>/scripts/ask.mjs 飞书 收款       # 按关键词排序，最多 8 条
node <skill 目录>/scripts/ask.mjs --check        # 列出 README 漏分组的 skill
```

- 关键词用用户原话里的名词，中英都试；无匹配时换同义词再查一次，仍无就如实说“仓库里没有”，再转 `skill_tiers.py find`。
- 脚本找不到仓库时，按其报错设置 `WEICOZ_SKILLS_REPO`。
- 候选不止一个时，读前 2–3 个的 `SKILL.md` 开头和 description，按适用条件区分，不凭名字猜。

## 3. 回答格式

- 首句给推荐的 skill 名和一句理由。
- 有相近候选时，用一行说明它们的区别和各自何时用。
- 写出调用方式：`/<name>`（Codex 为 `$<name>`）；调用被拒或找不到时读 `~/.agents/skill-tiers/library/<name>/SKILL.md` 执行。
- 用户只要清单时，原样给脚本的分组输出，不加评价。

## 4. 维护

新增 skill 后在仓库 README 的对应 `####` 分组表里加一行；`ask.mjs --check` 退出码 1 表示有漏分组。
