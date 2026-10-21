---
name: weicoz-first-keyword-free-tools
version: 1.0.0
description: 用 Google Keyword Planner、Ubersuggest、AnswerThePublic 和 Google 搜索，帮工具站或 SEO 新手从一个种子词里选出“值得先做的第一个关键词”。当用户说“帮我找第一个关键词”“用免费工具选词”“这个词值不值得做”“新站先做哪个长尾词”“给我从种子词筛一个可做词”时都应触发。尤其适合没有 Semrush 或 Ahrefs 付费账号，只想先锁定 1 个可落地关键词的人。
---

# First Keyword Free Tools

## Goal

用免费工具，在 `5-15` 分钟内从 `1` 个种子词里筛出 `1` 个优先落地的关键词。

重点是“先做哪个”，不是一次性做完完整 SEO 策略。

## Use When

- 用户只有 `1-3` 个种子词，想先锁定第一个落地方向。
- 用户没有付费 SEO 工具，或者只想先用免费工具做预筛。
- 用户想判断某个长尾词是否适合新站切入。

## Do Not Use Alone

- 如果用户要大规模批量扩词、完整需求挖掘、或 `GO / NO-GO` 商业判断，切到更大流程 skill，例如 `weicoz-demand-mining-kdroi` 或 `weicoz-brd-kdroi-fusion`。
- 如果用户已经有 Semrush 或 Ahrefs 全量 CSV，这个 skill 只负责首轮方向判断，不替代正式批量排序。

## Inputs

- `seed_keyword`: 一个种子词，例如 `pdf editor`
- `market`: 国家或地区，例如 `US`
- `language`: 语言，例如 `English`
- `site_stage`: 默认按 `新站 / 低权重站` 处理，除非用户明确说不是
- 可选：用户已经拿到的 Planner、Ubersuggest、AnswerThePublic、SERP 数据

## Tool Roles

按下面分工，不要混用结论：

- `Google Keyword Planner`: 看搜索量和广告竞争。它是官方数据源，但常只给区间。
- `Ubersuggest`: 看 SEO 难度 `KD`。按文章里的经验，免费版每天大约只能查 `3` 次，所以只查少量候选词。
- `AnswerThePublic`: 挖用户真实问题、限制条件、修饰词。按文章里的经验，免费版每天大约只能查 `1` 次，不要浪费在泛词扩写上。
- `Google 搜索`: 看首页竞争结构、广告、是否存在小站切口。

更多速查规则见 [references/method-cheatsheet.md](references/method-cheatsheet.md)。

## Core Formulas

只在有对应数据时使用，不要硬算。

### 1. KDRoi

`kdroi = monthly_search_volume x CPC / KD`

用途：

- 当你同时有 `搜索量 + CPC + KD` 时，用它做候选排序。
- 值越大，说明“需求规模 x 商业价值”相对竞争度更好。

规则：

- `KD` 越低越好。
- `CPC` 越高，通常说明离钱更近。
- `KD = 0` 时，不要直接相信“毫无竞争”，必须再做 SERP 人工验证。

### 2. KGR

`KGR = allintitle_result_count / monthly_search_volume`

用途：

- 没有 `KD` 时，用它代替竞争度预判。
- 在 Google 搜索 `allintitle:"keyword"` 获取分子。

规则：

- `< 0.25`: 对新站友好
- `0.25 - 1`: 需要再看 SERP
- `> 1`: 通常不适合第一批切入词

## 3-D Filter

新站默认按这三维筛选，不要一上来追大词。

### 1. 搜索量

- 优先 `50-1000 / 月`
- 搜索量太大，往往意味着首页已被大站占满
- 搜索量太小也不是直接淘汰，要结合意图强度看

### 2. 竞争度

- 优先 `KD 0-20`
- 没有 `KD` 时，优先 `KGR < 0.25`
- 无论 `KD / KGR` 多漂亮，都要再做一次 SERP 手工验证

### 3. 变现潜力

- 工具站优先功能型词，而不是泛内容词
- 搜索结果里有广告，是正向信号
- `CPC > 0.1` 是正向信号，不是唯一标准

## Keyword Pattern Bias

优先看这些模式：

- `[功能] online free`
- `best [类别] tool`
- `[功能] tool`
- `how to [功能]`
- `[竞品] alternative`

如果用户还没有种子词，优先从这些财富关键词展开：

- `Calculator`
- `Converter`
- `Generator`
- `Translator`
- `Editor`
- `Maker`

## Workflow

### Step 1 - Planner 扩词

- 让用户在 Keyword Planner 里输入 `seed_keyword`
- 保留 `Keyword / Avg monthly searches / Competition`
- 如果只看到搜索量区间，用 `Forecast` 标签页把 CPC 出价拉高，再看 `Impressions` 作为更细的近似值
- 先筛出 `搜索量 50-1000` 的词

### Step 2 - Ubersuggest 查难度

- 只挑 `3` 个最有潜力的词去查 `KD`
- 默认按“每天约 `3` 次免费查询”来规划，不要先查一大堆；如果产品规则变了，以当日界面为准
- 新站优先 `KD 0-20`

### Step 3 - AnswerThePublic 挖真实需求

- 看 `who / what / where / when / why / how`
- 默认按“每天约 `1` 次免费查询”来使用，只在已经缩到一个主题后再查；如果产品规则变了，以当日界面为准
- 重点提取用户的限制词和不满词，例如：
  - `without login`
  - `no watermark`
  - `safe`
  - `without losing quality`
- 这些词常常比泛词更适合新站切入

### Step 4 - Google SERP 验证

对每个候选词检查：

- 前 `10` 名里有多少 `DR 80+` 或强品牌大站
- 有没有独立站、个人站、小众工具站排进去
- 有没有广告
- 搜索结果是否已经把需求满足得很完整，导致切入空间很小

如果当前拿不到 `DR` 数据，就用下面的 proxy：

- 官方文档、超强品牌官网、大型媒体、大平台聚合页，统一视作“强站”
- 小众工具站、独立站、个人站、论坛帖混排，统一视作“仍有切口”

默认判断：

- 前 `10` 名里如果有 `3` 个以上 `DR 80+` 强站：偏难
- 有小站混排：可切
- 有广告：偏有商业价值

### Step 5 - 锁定第一个关键词

综合判断后只选 `1` 个，不要贪多。

优先级：

1. 意图最明确
2. 竞争最低
3. 变现信号最好
4. 最适合先做出 `1` 个单页工具

## Anti-Patterns

- 只看搜索量，不看竞争度
- 选过于宽泛的词，例如只做 `pdf editor`
- 忽略广告、`CPC`、功能型意图
- 免费工具拿到一点数据就直接下结论，不做 SERP 验证
- 一次同时选 `10` 个词，结果没有一个真正开做

## Output Protocol

始终按这个结构输出：

- `Goal`: 这轮要从哪个种子词里筛第一个关键词
- `Verify`: 候选词数据、`KD / KGR`、SERP 观察、最终选择原因
- `Next`: 下一个动作，默认是“围绕该词搭首个落地页或工具页”
- `Blocker`: 缺少哪个工具数据、地区数据或人工确认

候选词表至少包含这些列：

- `Keyword`
- `Search Volume`
- `KD or KGR`
- `CPC / Ads Signal`
- `ATP Insight`
- `SERP Verdict`
- `Pick?`
- `Why`

## Default Recommendation Style

- 默认先给 `1` 个最终词 + `2` 个备选词
- 每个判断都要说明“为什么”，不要只给分数
- 如果数据不足，明确标注是 `proxy judgment`，不要伪装成精确结论

## Example Prompts

- `帮我用免费工具从 pdf editor 里筛出第一个可做关键词`
- `我没有 Semrush，只能用 Keyword Planner 和 Google 搜索，帮我选一个新站先做的词`
- `种子词是 background remover，帮我判断先做哪个长尾词最稳`
