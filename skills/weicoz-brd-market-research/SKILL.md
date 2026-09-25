---
name: weicoz-brd-market-research
description: 用 3 小时 BRD 流程评估独立开发产品机会并输出 GO/NO-GO 决策，默认赛道是 AI 工具、出海、SaaS（含 Chrome 插件和各类平台插件）。Use when deciding whether to build a new AI SaaS, plugin, extension, validating a pivot, or re-checking demand before coding MVP. Includes demand trend checks, competitor pain mining, ICP and willingness-to-pay validation, TAM/SAM/SOM sizing, pricing strategy, risk scoring, and evidence-based final decision. When keyword KD / Volume / CPC data is needed, use weicoz-semrush-ego-browser first.
---

# BRD Market Research

## Overview

执行一套强约束的 6 步调研流程，目标是用最短时间避免做出“没人要”的产品。
核心产物是带证据链接的 BRD 文档和 GO/NO-GO 决策，不是泛泛分析。

## Default Track Scope

- 默认对象：AI 工具、海外市场、SaaS 模式。
- 默认产品形态：Web App、API、Chrome Extension、平台插件（如 Shopify/Figma/Notion/Slack/VS Code 等）。
- 非电商插件场景同样适用；电商只是可选垂直，不是前置条件。

## Quick Start

1. 先初始化调研工作区：
```bash
scripts/init_research_workspace.sh <project-slug> [output-dir]
```
2. 按 [references/query-pack.md](references/query-pack.md) 执行检索。
3. 实时把证据记录到 `evidence/evidence-log.csv`，禁止只写结论不留来源。
4. 使用 [references/brd-template.md](references/brd-template.md) 填写 BRD。
5. 填写 `outputs/scoring-input.json`，运行：
```bash
scripts/score_go_no_go.py outputs/scoring-input.json
```
6. 在 BRD 中写出最终决策、风险和 30 天执行计划。
7. 完成后必须将最终结果另存为调研工作区 `outputs/` 目录下的 Markdown 文件。
   - 支持统一命名：`market-research-report-YYYY-MM-DD-HHMMSS.md`
   - 也支持主题命名：`<topic-slug>-YYYY-MM-DD-HHMMSS.md`
   - 示例：`market-research-report-2026-04-23-010300.md`

## Tooling Rules

- 浏览器优先级固定为 `ego-browser` -> `browser-skill` -> `@Chrome`；只有当前工具不可用或确认无法完成当前能力时才进入下一层，并记录失败信号。
- `ego-browser` 通过 `ego-browser nodejs`、同一 task space 和最终独立的 `completeTaskSpace(..., { keep: false })` 执行；`browser-skill` 必须完整执行 `bsk session start` -> 操作 -> `bsk session stop`；`@Chrome` 遵循 `chrome:control-chrome` 的 browser-client 工作流。

- 优先使用可复验的公开来源：Google Trends、SimilarWeb、G2、Capterra、Trustpilot、Reddit、Product Hunt、Chrome Web Store、Statista、Crunchbase。
- 网页访问先走上述浏览器优先级；失败判定包括持续 403/429、验证码/风控拦截、页面正文为空、关键字段缺失、登录态或复杂交互阻塞。
- 触发兜底时必须记录：失败页面、失败信号、重试次数、下一层结果。
- 每条关键结论至少要有 2 个独立来源交叉验证，或明确标记为“单来源低置信度”。
- 默认先用英文关键词检索（海外市场主语料），仅在需要补充区域市场时追加当地语言关键词。
- 如果调研需要关键词 `KD / Volume / CPC / KDRoi`，优先调用 `weicoz-semrush-ego-browser` 从 Semrush Keyword Magic 页面导出第一页过滤结果；只在拿不到真实 SEO KD 时，才使用 Google Ads / 免费工具 proxy，并显式标注不是标准 KD。

## 6-Step Workflow (3 Hours)

### Step 1 - Demand Trend Gate (5-20 min)

目标：回答“需求是否存在且在增长”。

执行：
- 如果当前方向还没有关键词数据，先用 `weicoz-semrush-ego-browser` 获取候选词的 `Volume / KD / CPC / KDRoi`，保存到工作区 `outputs/semrush-keywordmagic-page1.csv` / `.json`。
- 搜主关键词（例：`remove background online`）看 3 年趋势。
- 拉长到 5 年验证是否临时性需求。
- 看 `Related Queries` 找高增速细分。
- 记录高热地区与语言分布。
- 若是插件产品，额外加入插件意图词（例：`chrome extension`、`shopify app`、`figma plugin`）。

验收：
- 输出 3 个判断：趋势方向、主战场地区、增长最快细分。
- 若趋势持续下降，必须写“下降原因假设”：市场萎缩或被替代。

### Step 2 - Competitor Pain Mining (60 min)

目标：定位“用户愿意付费但不满意”的缺口。

执行：
- 用四路搜索法采样：求助、吐槽、替代、交易。
- 平台至少覆盖：评价站 + 社区 + 应用商店三层。
- 重点读 1-2 星与 3-4 星评论，不只读 5 星好评。
- 提取痛点词频：`expensive`、`overpriced`、`slow`、`buggy`、`frustrating`、`credits`、`limit` 等。

验收：
- 得到“痛点证据表”：痛点、频次、用户身份、来源链接、是否可被你解决。
- 仅当同一痛点在 >=2 平台且累计 >=3 次时，标记为“真实痛点”。

### Step 3 - ICP & Willingness To Pay (20-40 min)

目标：锁定一个愿意付费的核心人群，而不是“所有人”。

执行：
- 从证据中抽取高频身份（如独立开发者、增长运营、内容团队、电商卖家、客服团队）。
- 写 1 个可执行画像：工作流、现用方案、月支出、最大痛点、触发购买条件。
- 用社区帖子或历史讨论估算心理价位区间。

验收：
- 画像必须包含“当前已支付给谁、每月花多少、可接受替代价位”。
- 若付费意愿证据不足，标记为“高风险待验证”。

### Step 4 - Market Sizing (20-30 min)

目标：从大盘和可触达盘两个视角评估空间。

执行：
- 自上而下：查行业报告得到 TAM 增速。
- 自下而上：用竞品流量/转化率/ARPU 粗估体量。
- 计算 TAM/SAM/SOM，SOM 用获客漏斗倒推，不拍脑袋写“拿 1% 市场”。

验收：
- 明确写出假设来源与计算公式。
- 乐观/中性/保守三档都要给，默认以保守档决策。

### Step 5 - Pricing & Unit Economics (20-30 min)

目标：形成可卖、可续费、可毛利的定价结构。

执行：
- 拉竞品价格带，使用中位数策略，不盲目最低价。
- 设计 `Free + Pro + API`（或等价）分层，并写额度逻辑。
- 估算单次成本、毛利和回本周期。

验收：
- 定价必须能解释：为何不做最低价、为何该价位对目标用户是“划算”。
- 保守营收场景下仍应覆盖基础成本，否则标记为 NO-GO 候选。

### Step 6 - Decision (10-15 min)

目标：在时限内完成可执行决策。

执行：
- 按 [references/go-no-go-scorecard.md](references/go-no-go-scorecard.md) 填写条件。
- 用 `scripts/score_go_no_go.py` 计算建议结果。
- 输出 30 天行动计划（渠道、实验、里程碑、止损点）。

验收：
- 给出 `GO / NO-GO / HOLD` 三选一，不允许“继续看看”。
- 每个结论都可追溯到证据日志。

## Output Protocol

过程和结论统一用以下结构输出：

- Goal: 当前阶段要回答的问题。
- Verify: 已验证事实、证据来源、置信度。
- Next: 下一步动作与时间盒。
- Blocker: 超过一个工作时段无法推进时必须显式声明。

另外，交付时必须同时满足以下落盘要求：

- 必须输出一份 `.md` 文件到调研工作区的 `outputs/` 目录。
- 文件名支持两种规则（二选一）：
  - 统一命名：`market-research-report-YYYY-MM-DD-HHMMSS.md`
  - 主题命名：`<topic-slug>-YYYY-MM-DD-HHMMSS.md`
- 日期时间格式建议使用 `YYYY-MM-DD-HHMMSS`，便于排序与检索。
- 若用户已指定文件名规则，以用户规则优先。

## Quality Bar

- 不做“只看一个平台”的单点判断。
- 不做“只看好评”的偏差判断。
- 不写“用户愿意付费”这种无金额、无证据的空话。
- 不把调研拖成无限期；3 小时到点必须决策。

## Resources

- [references/query-pack.md](references/query-pack.md): 四路搜索关键词包与时间分配。
- [references/evidence-log-template.csv](references/evidence-log-template.csv): 证据采集模板。
- [references/brd-template.md](references/brd-template.md): BRD 主模板。
- [references/go-no-go-scorecard.md](references/go-no-go-scorecard.md): 决策与打分规则。
- [references/scoring-input.example.json](references/scoring-input.example.json): 打分脚本输入示例。
- `scripts/init_research_workspace.sh`: 一键初始化调研目录。
- `scripts/score_go_no_go.py`: 依据规则生成 GO/NO-GO/HOLD 建议。
