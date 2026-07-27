---
name: weicoz-reddit-pain-evidence
description: |
  从 Reddit 挖掘真实用户痛点，并按“抱怨型痛点”标准判定“真需求”。当用户说“去 Reddit 找真实痛点”“如何判断 Reddit 用户痛点是真痛点”“看评论区交叉验证需求”“整理 Reddit 用户需求证据”“不要只看标题，要看评论区”时使用本 skill。它负责 Reddit 搜索、thread 阅读、评论证据抽取、痛点判定和证据报告；不自动替代 Semrush/KDRoi、产品机会评估或商业决策，除非用户另外要求。
allowed-tools: Bash(bb-browser:*), Bash(rg:*), Bash(sed:*), Bash(mkdir:*), Bash(wc:*)
---

# Reddit Pain Evidence

用 Reddit 的真实帖子和评论区判断用户是不是在抱怨真实痛点。核心目标不是列 idea，也不是当裁判，而是先从抱怨里发现问题，再判断它是否真的存在、是否有现成凑合方案、情绪成本和价值锚点。

## 判断标准

先找“抱怨”，不要把“愿望”直接当痛点。判断一个 Reddit 话题是不是值得继续挖，优先看下面这几类信号。

### 1. 具体场景

不要停在“AI 工具不好用”“这个流程很烦”这种泛描述。要能说清楚：

- 什么人在做什么任务
- 卡在流程的哪一步
- 这件事为什么今天就卡住了
- 这个痛点是不是重复出现，而不是一次性吐槽

### 2. 情绪成本

真痛点通常带有明确的情绪和时间损耗，而不只是中性提问。重点找这类信号：

- 被浪费了多少时间
- 是不是已经试了很多次还失败
- 用户有没有明显烦躁、沮丧、厌倦、崩溃、无奈等表达
- 有没有“太折磨了”“太耗时了”“我不想再手动做了”这类成本描述

### 3. 现成凑合方案

有真痛点的人，通常已经在用笨办法顶着：

- 手动复制粘贴
- 多标签页来回切
- Excel / Power Query / 脚本 / Zapier / n8n / VA / 外包
- 先凑合、先忍着、先手工做完

如果评论里能看到“我现在只能这样凑合”，这比单纯说“我希望有个产品”更接近真实痛点。

### 4. 价值锚点

用户有时候会无意间透露这个问题值多少钱，比如：

- 愿意花钱买时间
- 愿意加班、熬夜、周末处理
- 愿意为此换工具、找人、买服务

这不一定要是明确报价，但至少要能看出“这个问题值得被付出真实成本解决”。

### 危险信号

下面这些通常不能直接算真痛点：

- 纯提问型帖子，例如“有什么最好用的工具吗”
- 只有标题热闹，正文没有具体流程和成本
- 只有 OP 一个在抱怨，评论区没有同类经历
- 评论只有泛泛建议，没有新增痛点信息
- 话题更像信息搜索、选品咨询、或灵感征集，而不是正在流血的工作流卡点

判断时记住一句话：你是在翻石头，不是在当裁判。

## 证据原则

只把“实际读过的 Reddit thread 和评论”写成证据。评论区是用来找佐证和反证的，不再设置固定人数门槛。

## Tool Routing

优先尊重用户指定工具。

- Reddit 搜索和 thread 阅读：默认优先使用当前环境自带的搜索/浏览工具；如果拿不到搜索结果、thread 正文或评论，再用 `bb-browser` 兜底。
- 用户明确指定 `bb-browser`：使用本机 `bb-browser`，优先 `reddit/search` 和 `reddit/thread`。
- 用户指定其他浏览器/搜索工具：按用户指定工具执行。
- 用户没有指定工具：按当前项目/环境的浏览器默认规则执行。

`bb-browser` 兜底命令：

```bash
bb-browser site reddit/search "<query>" --subreddit <subreddit> --sort comments --time year --count 20 --json
bb-browser site reddit/thread <reddit_thread_url> --json
```

如果 `bb-browser` 报 `No page target found`，先确认 daemon 和 tab：

```bash
bb-browser status
bb-browser tab
bb-browser tab new https://www.reddit.com
```

## Step 0: Define The Search Job

先判断用户有没有给主题。

- 有明确赛道：围绕该赛道找 pain phrase 和 workflow phrase。
- 没有明确赛道：默认覆盖小企业、Excel/财务、电商、求职、创作者、客服/运营等高痛点人群。
- 用户给了数量：按用户数量找。
- 用户没给数量：默认找 5-10 个候选痛点，最终只保留达标方向。

默认门槛：

- `time = year`
- `sort = comments` 或 `relevance`
- 优先英文 Reddit 证据

## Step 1: Build Search Scope

不要从产品名出发，要从抱怨词和工作流词出发。

高信号 subreddit 示例：

- 小企业/运营：`smallbusiness`, `ecommerce`, `shopify`
- 表格/财务：`excel`, `bookkeeping`, `Accounting`
- 求职：`resumes`, `jobs`, `recruitinghell`
- 创作者：`podcasting`, `youtubers`, `EtsySellers`
- 软件工作流：`SaaS`, `Entrepreneur`, `freelance`

高信号 query 模式：

```text
"manual" + workflow
"takes forever" + workflow
"drowning in" + task
"spending hours" + task
"without going crazy" + task
"how do you handle" + task
"is there a better way" + task
"too expensive" + tool/category
"still doing this manually" + task
```

优先搜窄任务：

- 好：`PDF invoices to Excel`, `bank CSV clean`, `tracking emails`, `customer support 50 inquiries`
- 差：`AI business ideas`, `automation`, `productivity`

## Step 2: Collect Candidate Threads

每个候选 thread 先记录：

- title
- subreddit
- URL
- score
- comment count
- OP pain preview
- 为什么值得读评论

不要把搜索结果直接当证据。搜索结果只是候选池。

候选选择标准：

- 评论数较多，优先 20+。
- 标题和 OP 都有具体任务、数量、时间成本、工具限制或情绪词。
- 看起来不是纯推广、纯 meme、纯新闻、纯观点辩论。

## Step 3: Read Thread And Extract Comment Evidence

打开 thread 后同时读：

1. OP：痛点、场景、已有尝试、时间/金钱成本，先判断这是“抱怨”还是“许愿”。
2. 评论：不同用户是否补出了具体场景、成本、替代方案或反证。
3. 替代方案：人工、VA、脚本、Excel/Power Query、Zapier/n8n、SaaS、外包、模板。
4. 反证：评论是否质疑这是伪需求、广告贴、或已有工具足够。

评论证据不按固定人数计数，但必须能支撑或推翻上面的判断标准。

排除：

- AutoModerator / bot
- OP 自己的重复回复
- `[deleted]` / `[removed]`
- 纯赞同但没有新增信息的评论
- 明显推销但没有真实使用细节的评论

可计入：

- 用户描述自己也有同类工作流。
- 用户给出自己当前替代方案。
- 用户提到具体时间、成本、频率、工具、失败原因。
- 用户指出风险或边界，例如数据隐私、精度、格式变化。

## Step 4: Classify Evidence Strength

给每个方向标一个结论：

| 等级 | 标准 |
|---|---|
| 真痛点 | 有具体场景、明显情绪成本、现成凑合方案或价值锚点中的多个信号，且危险信号不占主导 |
| 待补证 | 有抱怨，但场景、成本、替代方案或价值锚点不够具体 |
| 淘汰 | 更像愿望、提问、信息搜索，或危险信号占主导 |

注意：评论多不等于需求强。要看评论是否真的补出了痛点细节，而不是只在凑热闹。

## Step 5: Write A Narrow Wedge

每个达标方向必须写成窄 wedge。

模板：

```text
帮 [具体用户] 在 [具体场景] 把 [痛苦任务] 变成 [具体结果]。
```

好：

- 帮小企业 admin 把每周 50 张 PDF 发票抽取成可校验 Excel。
- 帮多银行账户用户把不同 CSV 统一成一个 ledger。
- 帮 Shopify 小店把 tracking 邮件变成可审核 AI 草稿。

差：

- AI 财务助手
- AI 客服系统
- AI 自动化平台

## Step 6: Report Format

默认把报告落盘到当前工作区：

```text
outputs/reddit-pain-evidence-YYYY-MM-DD.md
```

报告结构：

```markdown
# Reddit 真实痛点证据报告

日期：YYYY-MM-DD
工具：...
证据标准：按“抱怨型痛点”标准判断，并记录评论佐证/反证

## 方法摘要

## 总结论

## 候选痛点清单

| 优先级 | 痛点方向 | 目标用户 | Reddit 证据 | 判断 |
|---|---|---|---:|---|

## 1. [痛点方向]

### 原帖

### 痛点

### 评论佐证 / 反证

### 具体场景

### 情绪成本

### 现成凑合方案

### 价值锚点

### 危险信号

### 反复出现的词根

### 可做的第一刀 MVP / 待验证 wedge

## 待补证 / 淘汰方向

## 建议下一步

## Completion Audit
```

每个方向的评论部分要列出足够支撑判断的评论摘要。不要长篇复制评论原文，简短概括即可。

## Quality Bar

- 不把“有哪些来源可用”写成“我实际读了哪些文件”。
- 不把搜索结果当证据。
- 不只看 OP，不读评论区。
- 不把点赞/score 当需求强度。
- 不把评论数量当硬门槛。
- 不为了凑数量把待补证方向放进主列表。
- 不把泛方向写成产品机会；只写窄工作流。
- 不编造付费意愿。没有付费证据就写“付费证据不足”。
- 不自动做商业 GO/HOLD/NO-GO；如需商业判断，再调用相应产品机会 skill。

## Completion Audit Template

报告末尾附：

```markdown
## Completion Audit

- 搜索工具：...
- 实际读取 thread：N 个
- 明确判定为真痛点的方向：N 个
- 待补证/淘汰方向：N 个
- 每个主方向都有 thread URL：是/否
- 每个主方向都写清了具体场景 / 情绪成本 / 凑合方案 / 价值锚点 / 危险信号：是/否
- 是否只看标题：否
- 输出文件：outputs/...
```

## Example User Requests

会触发本 skill 的请求：

- “去 Reddit 找一些真实用户痛点。”
- “帮我看看这个赛道 Reddit 上有没有真需求，别只看标题。”
- “用 Reddit 评论区验证这个 pain point 是不是伪需求。”
- “整理 Reddit 用户抱怨，输出证据表，先不要做商业判断。”
