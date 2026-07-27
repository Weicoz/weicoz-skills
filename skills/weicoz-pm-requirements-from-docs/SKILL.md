---
name: weicoz-pm-requirements-from-docs
description: Use this skill when the user provides customer requirement documents, DOCX/PDF/files, business model notes, marketing reward plans, or says to整理需求/PM需求文档/商业模式解释/玩法/报价工期. This skill turns raw customer materials into a concise product-manager-readable requirements document with business model, industry terms, flows, identity rules, reward formulas, settlement cycles, open questions, and rough quote/timeline. Use it especially when the user complains output is too long, asks for报价/工期, or needs a document suitable for client confirmation.
---

# PM Requirements From Docs

Turn messy customer docs into a short PM-readable requirements document. Prioritize clarity, business logic, formulas, and decision points. Do not produce a document longer than source material unless user explicitly asks for exhaustive detail.

## When to use

Use when user asks to:

- 根据 doc/docx/pdf 整理需求文档
- 输出适合产品经理看的需求
- 解释商业模式和玩法
- 梳理业务流程图
- 加身份、升级、奖励、结算周期
- 加报价和工期
- 把客户宣传资料变成可开发需求

## Core rule

The output should be more useful than the source, not longer than the source.

Default target:

- If source is short: keep final document under source length or close to it.
- If source is long: write executive PM version first, then optional appendix only if user asks.
- Avoid repeating page-level feature lists unless they affect business flow.
- Always surface contradictions and missing decisions.

## Workflow

1. Extract source text.
   - For `.docx` on macOS, use `textutil -convert txt`.
   - If `textutil` fails, unzip the DOCX and read `word/document.xml`; if that also fails, ask user for pasted text or a readable export.
   - If tables are flattened, still reconstruct from headings and adjacent rows.
   - Keep source line count in mind for output length.

2. Identify business primitives.
   - Product sold.
   - Price and payment rules.
   - User identities.
   - Upgrade conditions.
   - Rewards and formulas.
   - Settlement timing.
   - Trading loops.
   - Admin controls.
   - Risk and unclear rules.

🔴 CHECKPOINT: If the source cannot be read, or if less than 60% of requested fields can be inferred from the source, stop and ask for a readable file or missing business rules. Do not fabricate rules to fill gaps.

3. Set length and scope.
   - Count source lines or estimate source size.
   - Set a target shorter than source for normal PM brief.
   - If user asks for exhaustive detail, create main brief plus appendix instead of bloating the main document.
   - If quote/timeline is requested but scope is unclear, state explicit assumptions before giving ranges.

4. Write concise PM document.
   - Start with one-sentence project summary.
   - Add industry terms near top.
   - Explain business model and gameplay.
   - Add identity and upgrade table.
   - Add reward table and formulas.
   - Add ASCII flows.
   - If the deliverable includes a `需求文档`, the document must contain at least one explicit ASCII business flow diagram in the main body.
   - Add feature scope.
   - Add open questions.
   - Add quote/timeline if useful or requested.

🔴 CHECKPOINT: Before finalizing, compare the document against user-named requirements. If any named item is missing, add it or mark it “需确认”.

🔴 CHECKPOINT: If the output is a `需求文档`, verify that the file contains at least one ASCII business flow section such as `核心业务流程` or equivalent. If missing, add it before finalizing.

5. Verify coverage.
   - Search final file for required sections.
   - Check line count.
   - If output grew too long, compress before final.

## Failure handling

| Trigger | First action | Fallback |
| --- | --- | --- |
| Source file unreadable | Try `textutil`, then DOCX XML extraction | Ask user for pasted/exported text |
| Source tables flattened | Rebuild tables from nearby rows and headings | Mark uncertain rows as “需确认” |
| Reward formula missing | Derive only if source gives numbers and base amount | Write “公式需确认”，do not invent |
| Multiple conflicting formulas | Keep both source claims in 待确认重点 | Use no single formula as final truth |
| Output longer than source | Compress feature lists and prose first | Move detail to appendix only if user asks |
| Quote requested but scope unclear | Use phased estimate with assumptions | Mark hardware/API/legal/payment exclusions |
| Business model appears legally risky | Add risk note in PM 判断 / 待确认重点 | Do not give legal conclusion |

## Required document structure

Use this structure unless user asks otherwise:

```markdown
# [项目名] PM 需求简版

日期：[YYYY-MM-DD]

来源：
- [文件 1]
- [文件 2]

## 1. 项目一句话

## 2. 行业名词解释

## 3. 商业模式与玩法

## 4. 身份与升级规则

## 5. 奖励与结算

## 6. 核心业务流程

## 7. 产品功能范围

## 8. 待确认重点

## 9. 报价与工期预估

## 10. PM 判断
```

If no quote requested, omit section 9 and renumber PM 判断.

## Section guidance

### 1. 项目一句话

Explain in 1-2 short paragraphs:

- What system is being built.
- How user spends money.
- How user receives value.
- What internal unit or asset tracks reward.

Example:

```markdown
这是一个“卖 AI 智能盒 + 推广拉新 + 优惠券循环交易 + 积分奖励 + 代理分润”的业务系统。
```

### 2. 行业名词解释

Use a compact table. Include only terms needed to read later sections.

Typical terms:

- 平台积分 / 福豆 / 金豆
- 优惠券 / 进货券
- 委托代售
- 平台回购
- 双轨 / 链动 / 滑落
- 左区 / 右区
- 见点奖
- 级差分润
- 分红池
- 分红权
- 出局

### 3. 商业模式与玩法

Explain:

- Platform sells what.
- User buys why.
- How loop continues.
- Where platform/user value comes from.

Use one ASCII closed-loop diagram.

```text
用户购买产品
  -> 获得权益/券/积分
  -> 继续提货/转卖/回购
  -> 新订单产生新权益
  -> 奖励和结算进入积分账户
```

### 4. 身份与升级规则

Must include:

- Identity table.
- Obtain conditions.
- Upgrade conditions.
- Special conditions.

Identity table format:

```markdown
| 身份 | 获得条件 | 分润比例 | 权益 |
| --- | --- | ---: | --- |
```

Special conditions often include:

- Real-name verification.
- Address granularity.
- Permanent referral binding.
- Admin manual adjustment.
- Frozen account restrictions.
- History recalculation question.

### 5. 奖励与结算

Must include both summary table and formula table.

Reward summary format:

```markdown
| 奖励 | 谁拿 | 条件 | 金额 / 比例 | 结算 |
| --- | --- | --- | --- | --- |
```

Formula table format:

```markdown
| 奖励 | 公式 | 说明 |
| --- | --- | --- |
```

Formula checklist:

- Direct referral reward.
- Point/view/node reward.
- Agent differential commission.
- Daily device/computing/income split.
- Resale/consignment reward.
- Platform buyback reward.
- Dividend pool inflow.
- Dividend distribution.
- Dividend-right exit.
- Withdrawal deductions.
- Actual payout.

Use formulas like:

```text
直推奖 = 订单金额 x 直推比例
代理分润 = 订单金额 x (当前代理比例 - 下级已享比例)
算力分润 = 设备数 x 单台日收益 x 身份分润比例
当日入池 = 当日新增订单总额 x 入池比例 + 当日提现总额 x 提现入池比例
实际到账 = 提现金额 x 到账本金比例 x 扣税后比例
```

If source lacks formula details, write “需确认”，do not invent exact math.

### 6. 核心业务流程

Use ASCII flows. Keep them short.

Include flows for:

- Registration/referral if relevant.
- Purchase and benefit issuance.
- Reward positioning/chain/tree if relevant.
- Coupon/resale/buyback loop.
- Dividend flow if relevant.
- Device binding/income flow if relevant.
- Withdrawal flow if relevant.

Use this style:

```text
用户下单
  -> 支付成功
  -> 订单完成
  -> 发放权益
  -> 触发奖励/结算
```

Hard rule:

- If the deliverable is a `需求文档`, include at least one ASCII business flow in the main body.
- Better default is 2-5 short ASCII flows covering the main chain, not a single decorative diagram.
- Do not replace the ASCII flow with screenshots, Mermaid, or prose-only paragraphs unless the user explicitly asks for another format.

### 7. 产品功能范围

Keep as grouped bullets, not exhaustive pages.

Groups:

- 用户端
- 后台
- 结算/财务
- 风控
- 设备/硬件 if relevant

### 8. 待确认重点

Always include this. Customer docs often conflict.

Format:

```markdown
| 问题 | 文档冲突 / 不清楚点 | PM 需确认 |
| --- | --- | --- |
```

Common open questions:

- Reward base amount: original price or paid amount.
- Whether coupon loops forever.
- Whether admin changes recalculate history.
- Missing level/area fallback handling.
- Frozen reward display vs withdrawable reward.
- Settlement timing.
- Hardware API dependency.
- Legal/compliance concerns.

### 9. 报价与工期预估

Include when user asks or business doc needs sales handoff.

Use phased estimates:

```markdown
| 阶段 | 范围 | 工期 | 报价 |
| --- | --- | ---: | ---: |
| MVP 基础版 | [small scope] | 6-8 周 | 8-12 万 |
| 核心玩法版 | [reward/core flow] | 10-12 周 | 15-22 万 |
| 完整运营版 | [full matching/dividend/risk] | 14-18 周 | 25-38 万 |
```

Set ranges by complexity. State assumptions:

- Includes user app/mini-program, admin, backend, database, basic deployment.
- Excludes hardware R&D, protocol development, legal review, payment license handling.
- Hardware integration or third-party API uncertainty adds time/cost.

### 10. PM 判断

End with direct PM guidance:

- What the system really is.
- What rules must be confirmed before development.
- What to build first.
- What to postpone.

Example:

```markdown
这不是普通商城。核心不是页面，而是规则闭环：身份怎么来、奖励谁拿、积分怎么进出、权益什么时候失效、后台调整后历史账怎么算。
```

## Output rules

- Chinese by default.
- Keep short and readable.
- Prefer tables and ASCII diagrams.
- Avoid long explanatory prose.
- Do not overdesign architecture.
- Do not hide contradictions.
- Do not present unclear business rules as confirmed.
- If creating file in knowledge repo, prefer `${WEICOZ_OUTPUT_ROOT:-$PWD}/outputs/[项目名]-PM需求与商业模式说明-[date].md`.
- If the user explicitly wants the artifact saved into `jy-design`, or the current workflow is already routed into `jy-design`, then:
  - put the file inside the target project directory under `$WEICOZ_JY_DESIGN_ROOT`
  - prefer dated filenames such as `需求文档-YYYYMMDD.md`
  - if the project directory is newly created, prefer a dated directory name such as `项目名-YYYYMMDD`
  - do not leave the PM document in another repo's `outputs/` and then duplicate it later

## Anti-pattern blacklist

Do not:

- Produce a longer document than source for a PM brief.
- Copy the original document structure line by line.
- Turn every page/menu item into a long feature inventory.
- Hide conflicts by silently choosing one source rule.
- Invent reward formulas when source lacks base amount or percentage.
- Give one fixed quote without assumptions and scope boundaries.
- Treat积分/福豆/分红池/回购 as ordinary商城 fields; they are settlement/accounting rules.
- Omit settlement cycle for rewards that move money or points.
- Omit “待确认重点” because it makes the document look cleaner.
- Present compliance-sensitive mechanisms as safe; only flag risk and require confirmation.

## Verification checklist

Before final response, verify:

- File exists.
- Line count reasonable.
- Has industry terms.
- Has business model/play.
- Has identity and upgrade conditions.
- Has reward algorithms/formulas.
- Has settlement cycle.
- Has ASCII flows.
- If it is a `需求文档`, has at least one explicit ASCII business flow in the main body.
- Has quote/timeline if requested.
- Has open questions.
