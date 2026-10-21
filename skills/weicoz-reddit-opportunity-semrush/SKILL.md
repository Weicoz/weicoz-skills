---
name: weicoz-reddit-opportunity-semrush
version: 1.0.0
description: |
  从 Reddit 真实抱怨和评论交叉验证里挖产品需求，再用 Semrush 关键词门槛筛选，并输出带 GO/HOLD/NO-GO、MVP、商业化和执行建议的产品机会报告。
  当用户说“从 Reddit 找真需求”“找痛点并用 Semrush 验证”“Reddit + Semrush 需求挖掘”“生成机会报告”“找 10 个能做的 AI Web 产品方向”“用 weicoz-ai-product-opportunity / 刘小排视角判断需求”时使用本 skill。
  执行前要询问用户想找多少个需求/痛点，以及 Semrush 的 Volume/KD/CPC 筛选条件；如果用户不知道或不提供，默认找 10 个方向并使用内置 Semrush 阈值。
---

# Reddit Opportunity + Semrush Validation

用 Reddit 真实痛点做需求源，用 Semrush 做搜索意图过滤，再用产品机会框架和刘小排视角把方向收敛成可执行的 MVP 报告。

## Core Rule

不要只列 idea。每个最终方向都必须同时过三关：

1. Reddit 有真实帖子和评论区交叉验证。
2. Semrush 有至少一个匹配或可承接关键词过线。
3. 能收敛成 5-7 天内可做的 AI Web MVP。

如果某方向 Reddit 证据强但 Semrush 不过线，放入“被淘汰但需求真实的方向”，不要硬塞进最终榜单。

## Required Skill Routing

优先使用这些官方工具和本机业务 skill：

- Reddit 抓取和网页浏览：按 `ego-browser` -> `browser-skill` -> `@Chrome` 路由。
- Semrush：所有 Semrush 查询必须使用 `weicoz-semrush-ego-browser`。
- 产品机会判断：使用 `weicoz-ai-product-opportunity` 的结构。
- 刘小排视角：使用 `weicoz-liu-xiaopai-perspective` 的判断方式。

不要把 Semrush 主路径切回临时 DOM 脚本或手搓浏览器解析，除非 `weicoz-semrush-ego-browser` 明确不可用，并且要在报告里写明 fallback 原因。浏览器 fallback 只能按 `ego-browser` -> `browser-skill` -> `@Chrome` 逐级执行。

## Step 0: Ask For Parameters

执行前先问用户两个问题。不要问太多。

```text
你要找多少个最终需求/痛点？不提供默认 10 个。
Semrush 筛选条件要用什么？不提供默认 Volume > 500、KD <= 29、CPC > 0.1。
```

如果用户已经在请求里给了数量或筛选条件，直接采用，不再重复询问。

默认值：

- `target_count = 10`
- `min_volume = 500`
- `max_kd = 29`
- `min_cpc = 0.1`
- `market = US`
- `language = English keyword first`

Semrush 页面筛选语义要注意：

- `volume > minVolume`
- `kd < maxKd`
- `cpc > minCpc`

因此用户要求 `KD <= 29` 时，传给 adapter 的 `maxKd` 应使用 `30`。

## Step 1: Define Search Scope

先根据用户给的主题判断搜索范围：

- 用户给了明确赛道：围绕该赛道找 Reddit 痛点。
- 用户只说找 AI Web 产品机会：默认覆盖内容创作、求职招聘、电商卖家、学生/研究、创作者/小团队等高痛点人群。
- 用户指定国家/市场：Semrush 使用对应市场；没有指定默认 `US`。

每个子方向的 Reddit 查询应该围绕抱怨词和工作流词，而不是产品名幻想。

可用 query 模式：

- `site:reddit.com/r/<subreddit> "<pain phrase>"`
- Reddit JSON search：`https://www.reddit.com/search.json?q=<query>&sort=relevance&t=year&raw_json=1`
- Thread JSON：`https://www.reddit.com/<thread>/.json?limit=50&raw_json=1`

## Step 2: Collect Reddit Evidence

每个候选方向至少要记录：

- Reddit thread URL
- subreddit
- 原帖痛点摘要
- 评论区 3 个以上不同用户的交叉验证
- 原话词根，例如 `manual`, `takes forever`, `same questions`, `ATS`, `bulk upload`
- 为什么适合 5-7 天 AI Web MVP

证据门槛：

- 只看楼主吐槽不够，必须看评论区。
- 评论区只有泛赞同不够，最好有独立用户描述相同工作流、替代方案或成本。
- 优先保留“已经有人用模板、人工、脚本、表格、现有工具拼装解决”的痛点。
- 避免保留只有“这个 idea 听起来不错”的需求。

## Step 3: Build Candidate Pool

候选池数量建议是最终数量的 2-3 倍。例如最终要 10 个方向，先找 20-30 个候选。

候选方向要先写成窄 wedge，而不是泛品类：

- 好：`Master resume + JD -> 差异补丁 + bullet rewrite`
- 差：`AI 求职助手`
- 好：`图片 + CSV -> Shopify CSV listing draft`
- 差：`AI 电商运营平台`
- 好：`final audio -> transcript QA + publish-ready export`
- 差：`AI podcast tool`

## Step 4: Run Semrush Validation

对每个候选方向设计 2-5 个关键词：

- 直接需求词：用户会搜索解决方案的词。
- 模板/工具词：`template`, `generator`, `tracker`, `converter`, `checker`, `assistant`。
- 类别承接词：当直接词不过线但类别词和 Reddit 工作流一致时可保留，但要在报告中标注“承接词，不是最直接购买词”。

必须使用 `weicoz-semrush-ego-browser`。

推荐流程：

1. 用 ego-browser 打开 live result page，复用同一 task space。
2. 核对标题、URL 和 query，等待页面渲染。
3. 用 `snapshotText()` / `js()` 提取真实渲染表格，并验证筛选控件标签与返回行。
4. 每个 query 尽量使用独立结果 tab，不要乱复用不同 query 的 tab。

示例：

```text
ego-browser nodejs：打开 Keyword Magic URL，等待渲染，验证标题/URL/KD/CPC/行数，再提取表格。
```

如果使用 named flags：

```text
browser-skill fallback：bsk session start -> navigate/snapshot/evaluate -> bsk session stop。
@Chrome fallback：加载 chrome:control-chrome 后按 browser-client 工作流执行。
```

记录每个过线词：

```text
keyword: Volume / KD / CPC
```

如果某个方向没有过线词：

- 不要直接说“没市场”。
- 写成“本轮没有找到符合筛选条件的 Semrush 词”。
- 放入淘汰区或补证区。

## Step 5: Apply Product Opportunity Judgment

每个最终方向都按 `weicoz-ai-product-opportunity` 输出完整判断。不要只写一句。

必须包含：

```markdown
### ai-product-opportunity

#### 购买理由

#### 目标用户 / 场景 / 付费 / 问题

#### 需求证据

#### 供需失衡

#### 机会类型

#### MVP 最小闭环

#### 流量入口

#### 商业化方式

#### 主要风险

#### 结论

#### Next
```

判断原则：

- 购买理由必须回答：什么人，在什么场景，愿意花多少钱，解决什么问题。
- MVP 必须写清输入、处理、输出、付费点、反馈。
- GO/HOLD/NO-GO 不能只由搜索量决定，要结合 Reddit 证据、付费意图、交付难度和风险。

## Step 6: Apply Liu Xiaopai Perspective

每个最终方向都补一个 `weicoz-liu-xiaopai-perspective` 段落。不要只写一句。

结构：

```markdown
### liu-xiaopai-perspective

一句话结论：...

优先级动作：

- ...
- ...
- ...

风险点：

- ...
- ...

止损线：

- ...
- ...
```

内容要覆盖这 5 个维度中的关键项：

- 杠杆与单位经济：这个产品是不是省时间、省人力、可复用？
- 需求与分发真实性：用户在哪里已经表达痛点，如何低摩擦触达？
- SOP 密度：哪些步骤能标准化成 workflow？
- 模型/工具匹配：AI 负责什么，人工确认什么？
- 组织瓶颈/授权边界：哪些地方不能自动化承诺，必须人工把关？

## Step 7: Write Final Report

报告必须落盘为 Markdown。默认保存到 `${WEICOZ_OUTPUT_ROOT:-$PWD}`：

```text
${WEICOZ_OUTPUT_ROOT:-$PWD}/outputs/weicoz-reddit-opportunity-semrush-YYYY-MM-DD.md
```

如果用户给了项目目录，保存在该项目的 `outputs/` 下。

报告结构：

```markdown
# Reddit 真需求 + Semrush 过线机会报告

日期：YYYY-MM-DD

## 方法摘要

## 总结论

## 最终优先级

| 优先级 | 方向 | 明确第一刀 | 判断 |
|---|---|---|---|

## 1. [方向名]

### 方向定义

### Reddit 证据

### Semrush 过线词

### ai-product-opportunity

### liu-xiaopai-perspective

## 被淘汰但需求真实的方向

## 最建议的执行顺序

## Completion Audit
```

每个方向的“方向定义”必须写出第一刀：

- 只做什么
- 不做什么
- 核心承诺是什么

## Quality Bar

最终报告至少满足：

- 最终方向数量达到用户目标；如果没达到，要写明还差几个和原因。
- 每个最终方向都有 Reddit thread URL。
- 每个最终方向有 3 个以上评论区交叉验证点或明确说明证据不足。
- 每个最终方向至少有 1 个 Semrush 过线词；如果使用类别承接词，必须标注。
- 每个最终方向都有完整 `ai-product-opportunity` 段落。
- 每个最终方向都有完整 `liu-xiaopai-perspective` 段落。
- 每个方向都明确 `第一刀 MVP`，避免泛方向。
- 淘汰区保留真实但未过筛的方向，避免证据丢失。

## Completion Audit Template

报告末尾附：

```markdown
## Completion Audit

- 最终方向数量：N / target_count
- Reddit 证据：每个最终方向都有 thread URL 和评论交叉验证
- Semrush：每个最终方向都有过线词，筛选条件为 Volume > X、KD <= Y、CPC > Z
- ai-product-opportunity：N 个方向已补齐
- liu-xiaopai-perspective：N 个方向已补齐
- 输出文件：outputs/...
```

## Common Pitfalls

- 不要把“有哪些来源可用”写成“我实际读了哪些文件”。
- 不要只看 Reddit 帖子标题，不读评论区。
- 不要把搜索量大等同于可赚钱。
- 不要把通用大方向当最终方向，例如 `AI 求职助手`、`AI 电商工具`、`AI 学术助手`。
- 不要为了凑数量把没过 Semrush 的方向塞进最终榜单。
- 不要用旧 Semrush 临时脚本作为主流程。
- 不要让 `weicoz-liu-xiaopai-perspective` 只输出一句口号，它必须给动作、风险和止损线。
