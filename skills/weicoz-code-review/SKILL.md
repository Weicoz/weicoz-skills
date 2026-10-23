---
name: weicoz-code-review
version: 1.0.0
description: 省 token 的本地代码审查：审查某个比较点、提交区间或未提交改动，按规范与需求两条线找问题，再批量打置信分过滤误报。Claude Code 中整体 fork 给 Sonnet 执行，主对话只收最终报告；大改动或高风险改动才加派审查，打分用 Haiku。用于“审查/review 我的改动”“审一下这个分支/这几个提交”“weicoz-code-review”。不用于发布 GitHub PR 评论、安全专项审计（用 /security-review）、高风险最终把关（用 @gatekeeper）。
argument-hint: "[比较点|A..B] [--incremental] [--deep] [--cheap] [--full] [--spec <路径>]"
context: fork
agent: weicoz-cr-orchestrator
background: false
---

# weicoz-code-review

参数：$ARGUMENTS

你负责一次只读代码审查，最终报告直接交给用户。全程中文。除第 5 步的记录文件外，不得写入、提交或删除任何文件。

当前环境没有 Agent 工具、或不支持按调用指定 model 时：第 3、4 步自己完成，其余照做。

## 1. 准备（尽量合并成一两次 Bash）

**解析范围**
- 参数里的 `A..B`：直接使用。
- 单个 ref：视为 `<ref>..HEAD`。
- 无比较点：用 `git merge-base HEAD <默认分支>`（依次尝试 `@{upstream}`、`main`、`master`）到 HEAD，并合并 `git diff HEAD` 的未提交改动。
- `--incremental`：读 `$(git rev-parse --git-dir)/weicoz-code-review/last-sha`。该 SHA 不是 HEAD 的祖先（如 rebase 后）时，退回上一条规则，并在报告中注明。
- ref 无法解析：报告错误并停止。

**排除路径**：以下 pathspec 不进入审查，报告中注明已排除：
`':!*.lock' ':!package-lock.json' ':!pnpm-lock.yaml' ':!yarn.lock' ':!**/dist/**' ':!**/build/**' ':!**/vendor/**' ':!**/node_modules/**' ':!*.min.*' ':!*.map' ':!**/__snapshots__/**'`

**统计**：用 `git diff --numstat` 统计改动行数（增加 + 删除）与文件数。
- 无改动：输出“无可审查改动”并停止。
- 全部是 `.md` / `.txt`，且都不在 `skills/`、`prompts/`、`.claude/`、`agents/` 下，也不是 `CLAUDE.md`、`AGENTS.md`、`SKILL.md`：
  - 无 `--cheap` 时，输出“仅文档改动，已跳过（加 --cheap 用 Haiku 审）”并停止。
  - 有 `--cheap` 时，派 1 个 `weicoz-cr-reviewer`（model `haiku`，effort `low`）审查，再跳到第 4 步。

**风险扫描**：对 diff 的新增行与文件名执行 `rg -i`。关键词：
`mutex|lock\(|semaphore|race|atomic|thread|goroutine|Promise\.all|concurren|transaction|auth|permission|privilege|sudo|chmod|chown|token|secret|role|migrat|ALTER TABLE|DROP |schema|subagent|orchestrat|dispatch|spawn`
另外，`package.json` / `requirements*.txt` / `go.mod` / `Cargo.toml` 的依赖变化、`*.sql`、`migrations/` 也算命中。记录命中项。

**规范来源**：列出改动目录及其各级上级目录中的 `CLAUDE.md`、`AGENTS.md`、`CONTRIBUTING.md`，只取路径。

**需求来源**：`--spec <路径>` 指定的文件；无则用区间内的提交信息（`git log --format='%s%n%b'`）。

## 2. 审查

**读取预算**（自己和派出的审查 agent 都遵守）：
- 用 `git diff -U3 <范围> -- <排除 pathspec>` 读 diff。
- 需要上下文时，用 `rg -n` 定位调用点，再用 `sed -n 'a,bp'` 只读相关函数。
- 不整份读取超过 200 行的文件。

**分档**
- **小档**：改动 ≤200 行，且无风险命中。你独自完成两条线，不派 agent。
- **大档**：改动 >200 行，或有风险命中。
  - **必须**先派 1 个 `weicoz-cr-reviewer`（model `sonnet`，effort `medium`），不得省略。只传：范围、排除 pathspec、需求来源、风险命中项，以及 `--deep`（有则传）。它负责需求与缺陷线。
  - 你负责规范线，等它返回后合并去重。

**最低检查量**（两档都适用）：
- 每个新增或改动的函数，都要用 `rg -n` 查一遍调用点。
- 生成物（manifests、logs、快照类 JSON）只看 `--stat`，不读内容。

**规范线**
- 违反规范来源中的明确规则：引用文件与原句。
- 违背被改代码注释中写明的约定。
- 明显的重复，或遗漏可复用的已有实现。

**需求与缺陷线**（小档时由你负责）
- 逻辑错误、边界条件、空值与错误路径、调用方被破坏。
- 与需求或提交意图不符、缺失的需求、超出需求的改动。
- 只读语义的函数产生了写入，或者有副作用的操作缺少清理或保留策略。
- 硬编码的路径、地址、凭据。
- 新增或改变的行为没有对应测试。
- 改动的约定、分层、术语，没有同步到 README、ADR、AGENTS.md 等文档。

风险命中只决定档位和是否提示 gatekeeper；具体问题仍要写进问题列表。

**一律不报**
- 不在本次改动中的旧问题。
- lint、类型检查、格式化工具能发现的问题。
- 纯风格偏好。

## 3. 打分

- 无发现：跳过本步。
- 有发现：派 1 个 `weicoz-cr-scorer`（model `haiku`），一次传入全部问题，每条包含：
  - 编号、`路径:行号`、问题陈述；
  - 对应 diff 片段（≤30 行）；
  - 若引用了规范，附规范原句。
- 采用它返回的分数。≥70 分进入正文，<70 分只列标题。

## 4. 输出（默认 ≤300 字；`--full` 时不限条数）

```
范围：<范围>｜<N> 个文件，+<a>/−<d> 行｜已排除：<类别或"无">
档位：小档/大档｜风险：无 / 命中 <关键词或文件>

## 问题（≥70 分，最多 8 条）
1. [严重/高/中/低] 路径:行号 — 问题；建议：<改法>（<分数>）

## 低置信（<70 分）
- 路径:行号 — <标题>（<分数>）

另有 <N> 条省略，加 --full 查看。   ← 仅在超出上限时出现
建议 @gatekeeper 复核：<涉及点>     ← 仅在风险命中时出现
```

无发现时只输出一行：`未发现问题（范围：…，档位：…）`。只输出模板内容，不追加过程说明。

## 5. 记录

范围终点是 HEAD 时，把 `git rev-parse HEAD` 写入 `$(git rev-parse --git-dir)/weicoz-code-review/last-sha`，目录不存在就创建。这是唯一允许写入的文件。
