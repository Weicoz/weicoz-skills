---
name: weicoz-mode-commerce-research
description: Use this skill whenever the user asks to research "模式电商", 社群团购, 私域分销, 多层级批发/报单/团长体系, or wants to reverse-engineer a platform's business model, reward rules, user identities, business process, and how the process should be represented in a software system. Primary sources are 微信公众号, 小红书, and 知乎, but do not stop there; always widen to search engines, industry media, software-vendor breakdowns, complaint/legal/company records, and other credible channels when useful.
---

# 模式电商资料收集

## Goal

把一个模式电商品牌或项目拆成可执行的业务研究结果：

- 商业模式：货、钱、人、平台分别怎么流动。
- 用户身份：消费者、团长、代理、批发商、总代、平台、供应商等角色。
- 业务流程：从招募、建群、开团、下单、报单、结算、发货到售后。
- 奖励玩法：零售差价、级差、直推、团队奖、分红、晋升条件。
- 系统映射：后台应该有哪些模块、字段、状态、账本和风控点。

不要把它写成普通电商市场调研。重点是还原实际玩法和系统流程。

## Source Strategy

优先级是“主要渠道优先，多渠道交叉验证”，不是“只看某几个平台”。

Primary sources:

- 微信公众号文章：行业号、平台招商号、代理培训号、模式拆解号、投诉/质疑号。
- 小红书：用户体验、代理招募、笔记评论、实操截图、真实吐槽。
- 知乎：问答、专栏、讨论、争议和长文拆解。

Secondary sources:

- 搜索引擎结果页摘要和快照线索。
- 行业自媒体、搜狐号、百家号、今日头条、软件商模式拆解。
- 工商信息、司法/处罚/投诉平台、黑猫投诉、企查查/天眼查等。
- App、小程序、官网、招商页、直播/视频号/抖音资料。

Official sources are allowed only as baseline facts unless the user explicitly asks for official口径. If the user says不要官网, do not use官网 as primary evidence.

## Tool Routing

Respect the user's specified tool first.

**Do not use `bb-browser` for this skill.**

Use the following priority order for web research and article retrieval:

1. **Built-in web search tool (`WebSearch`)** — default first choice for all queries. Run broad and intent-specific queries in parallel, then use `FetchURL` to open high-value articles.
2. **`opencli`** — use when the built-in search returns insufficient results, or when you need site-specific commands (e.g. `opencli search`, `opencli site <domain>`). Load `opencli-usage` first if unfamiliar with available adapters.
3. **`web-access`** — use when `WebSearch` and `opencli` both fail, or when the task explicitly requires a browser-agent workflow. This skill wraps browser automation behind a unified interface.
4. **`agent-browser`** — use as the fourth fallback for logged-in browser tasks, form interaction, or JavaScript-heavy pages that the above tools cannot retrieve.
5. **`playwright`** / `playwright-cli` — use only as the final fallback when all other tools fail and a real browser session is absolutely required. Prefer `playwright-cli` over the MCP variants.

For 微信公众号 content, try the built-in `WebSearch` with queries like `site:mp.weixin.qq.com <品牌名> <关键词>` first. If that yields only snippets, escalate through `opencli` → `web-access` → `agent-browser` → `playwright`.

Use `FetchURL` to open high-value articles when possible. If an article is blocked, removed, or only the search snippet is available, record it as `snippet-only` evidence and lower confidence.

Do not use `mcp__claude-in-chrome__*` tools.

## Research Workflow

### 1. Frame The Questions

Start each run with a short research frame:

- Target: platform/brand/project name.
- Scope: model, roles, reward rules, system process, compliance risks.
- User constraints: e.g. no官网, 微信公众号优先, focus on system design.
- Freshness: note today's date and treat pricing/reward rules as time-sensitive.

### 2. Build Query Matrix

Run queries across several intent buckets:

```text
<品牌> 商业模式
<品牌> 模式 拆解
<品牌> 业务流程
<品牌> 团长 报单
<品牌> 建群 开团 流程 话术
<品牌> 奖励 奖金 分配 制度
<品牌> 小批发 中批发 大批发
<品牌> 晋升条件
<品牌> 资金流 信息流 商品流
<品牌> 传销 合规 风险 投诉
<品牌> 小红书
<品牌> 知乎
site:mp.weixin.qq.com <品牌> 报单 奖励
site:xiaohongshu.com <品牌> 团长 报单
site:zhihu.com <品牌> 模式
```

For each useful result, capture title, platform/account, URL, date if visible, and exact claim.

### 3. Separate Evidence From Inference

Classify every important claim:

- `confirmed`: repeated by multiple credible sources or directly visible in platform materials.
- `likely`: supported by several snippets/articles but no primary artifact.
- `weak`: only one source,招商软文, or search-snippet-only.
- `inference`: your own reconstruction from observed facts.

Never present reward ratios or层级条件 as certain if they came from one招商 article.

### 4. Reconstruct Four Flows

Force the model into four separate flows:

- 人流：谁被招募，怎么认证，怎么晋升。
- 信息流：素材、开团、订单、报单、团队业绩怎么传递。
- 资金流：消费者付款给谁，团长/上级/平台怎么结算。
- 货物流：谁备货、谁发货、退换货怎么回传。

This prevents confusing "source availability" with "actual business process".

### 5. Translate To System Design

After the research summary, convert the model into system modules:

- 身份层级：角色、上级链路、晋升条件、权限边界。
- 私域运营：群认证、群信息、素材中心、开团记录。
- 商品价格：消费者价、各层级拿货价、供货价、限价。
- 报单中心：代客录单、付款凭证、收货信息、订单归属。
- 结算账本：零售差价、级差、推广费、待结算、已结算、冲账。
- 履约售后：发货、物流、退货、补发、退款、收益回滚。
- 风控稽查：刷单、乱价、跨区、异常团队、资金凭证缺失。

## Evidence Log

Create or maintain an evidence log when the task is more than a quick answer. Use `references/evidence-log-template.md`.

Minimum fields:

- source platform
- source title/account
- URL
- publish date or access date
- claim category
- extracted claim
- confidence
- notes on bias or limits

## Report Template

Use `references/report-template.md` for substantial outputs.

For short chat answers, keep this structure:

1. 结论
2. 证据来源覆盖
3. 身份体系
4. 业务流程
5. 奖励/比例口径
6. 系统应该怎么体现
7. 风险和不确定项

## Quality Gates

Before answering, check:

- Did you avoid relying on官网 when the user asked for other channels?
- Did you search 微信公众号, 小红书/知乎, and at least one wider channel when the task is broad?
- Did you label reward ratios and晋升条件 by confidence?
- Did you separate business reality from system implementation advice?
- Did you cite or name the actual channels/articles used, not just say "网上资料"?
- Did you include clear next-step system modules if the user asks how to build it?

## Output Rules

- Prefer Chinese.
- Be direct and concrete.
- If data is weak, say exactly what is weak.
- Do not overstate legal compliance. Mark compliance discussion as risk analysis unless verified by authoritative legal/regulatory sources.
- If the user asks for implementation, turn the research into tables, state machines, ledger formulas, and module boundaries.
