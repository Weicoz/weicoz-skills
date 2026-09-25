---
name: weicoz-brd-kdroi-fusion
description: >
  先用 KDRoi（Volume x CPC / KD）做关键词可达性 Gate，再执行 6 步 BRD 市场调研并输出 GO/NO-GO/HOLD。
  用于出海工具站、AI SaaS、Chrome 插件、SEO 工具站、micro SaaS 的需求筛选与商业决策一体化评估。
  当用户提到选题验证、关键词机会、产品机会、BRD、市调、商业可行性、GO/NO-GO/HOLD、KDRoi、KD/Volume/CPC 时使用。
  需要真实 KD / Volume / CPC 时默认调用 weicoz-semrush-ego-browser 获取 Semrush Keyword Magic 数据；禁止编造 KD 或把 proxy 当标准 SEO KD。
---

# BRD + KDRoi Fusion

## Goal

把“选需求”和“做 BRD”串成一条流水线：
- 先筛掉难做或不赚钱的词；
- 再在通过 Gate 的方向上做深度商业验证。
- 最终给出可执行的 `GO / NO-GO / HOLD` 决策，而不是停在泛结论。

## Use When

- 你要做新产品选题，且不想只靠直觉。
- 你已经有关键词或词根，想判断“值不值得做”。
- 你需要最终给出 `GO / NO-GO / HOLD`，并附证据。
- 用户要求做 `BRD`、市场调研、产品机会验证、SEO 机会判断、出海工具站选题、AI SaaS 方向筛选。
- 用户给出旧报告并要求“不要和这些方向类似”时，把旧方向作为硬排除条件。

## Decision Rules

- `GO`：Step 0 真实 KD Gate 通过，Evidence Quality Gate 通过，有明确 ICP + WTP 证据 + 可切入 SERP/分发路径。
- `HOLD`：关键词或证据有潜力，但 KD 缺失、proxy 模式未完成 SERP 验证、WTP 不足、痛点证据不足、方向过宽。
- `NO-GO`：KD 不可达、SERP 被巨头/官方/强品牌完全垄断、痛点证据弱、没有 WTP、竞品已经充分满足且没有可切入口。

不得判定 `GO` 的情况：

- 只有 `Ads-KDRoi proxy`，没有真实 SEO KD，也没有 SERP 首页结构验证。
- 没有 `>=3` 条同类痛点且未覆盖 `>=2` 个平台。
- 没有可验证 WTP 证据。
- 只看到搜索量高，但用户场景、付费人群、MVP 切口不明确。
- 证据主要来自过时内容，且没有最近 `3-6` 个月补证。

## Quick Start

1. 初始化调研工作区：
```bash
scripts/init_research_workspace.sh <project-slug> [output-dir]
```

2. 先做 10 分钟预检（避免明显方向性坑）：
```bash
cat <workspace>/notes/preflight-checklist.md
```

3. 获取关键词 KD 数据。默认先使用 `weicoz-semrush-ego-browser`：
```text
用 ego-browser nodejs 打开 Keyword Magic live result page，复用同一 task space，验证标题/URL/渲染表格和筛选控件，再输出 CSV/JSON。
```

说明：
- 只改 Semrush URL 的 `q` 参数，保留 `db=us`、`filter`、`__gmitm`。
- 产出字段含 `keyword / volume / kd / cpc / kdroi`，可直接进入 KDRoi Gate。
- 如果已有 Semrush / Ahrefs / Keyword Planner CSV，可跳过本步。

4. 执行 KDRoi 排序（Step 0 Gate）：
```bash
python3 scripts/rank_kdroi.py \
  --in <workspace>/outputs/semrush-keywordmagic-page1.csv \
  --out <workspace>/outputs/keywords-ranked.csv \
  --min-kd 0 --max-kd 29 \
  --min-volume 200 --max-volume 10000 \
  --min-cpc 0.1 --top 20
```

4.1 如果拿不到 Semrush / Ahrefs / Keyword Planner CSV，走免费版 proxy Gate：
```bash
curl -L -s -A 'Mozilla/5.0' \
  "https://kwresearch.io/api/search.php?keyword=<keyword>" \
  > ./kw.html
```

从返回 HTML 里提取：
- `data-vol` -> Volume
- `data-cpc` -> CPC range
- `data-comp` -> Google Ads competition

再计算：
- `Ads-KDRoi proxy = Volume x CPC(mid) / AdsCompetitionProxy`
- 映射：
  - `LOW = 1`
  - `MEDIUM = 2`
  - `HIGH = 3`
  - `UNKNOWN = 4`

说明：
- 这是 `Google Ads / public tool proxy`，不是标准 SEO `KD`
- 它适合做“需求热度 + 商业意图”的免费初筛
- 它不能单独替代 SEO 难度判断，必须追加 SERP 人工验证

5. 把 Top 候选写入 `outputs/kdroi-gate.md`，并完成四步验证。

6. 基于 Gate 通过的方向，填写 `outputs/BRD.md`（Step 1-6）。

7. 先跑证据质量闸门，再更新评分输入：
```bash
python3 scripts/validate_evidence_gate.py \
  --evidence <workspace>/evidence/evidence-log.csv \
  --scoring <workspace>/outputs/scoring-input.json \
  --out <workspace>/outputs/evidence-gate-report.json
```

8. 计算建议：
```bash
python3 scripts/score_go_no_go.py <workspace>/outputs/scoring-input.json
```

9. 生成 BRD 自动草稿（可选）：
```bash
python3 scripts/generate_brd_skeleton_from_evidence.py \
  --evidence <workspace>/evidence/evidence-log.csv \
  --out <workspace>/outputs/BRD-draft-from-evidence.md
```

10. 一键串行执行（可选）：
```bash
scripts/run_fusion_pipeline.sh <workspace>
# 严格模式（证据闸门不过即中断）
scripts/run_fusion_pipeline.sh <workspace> --strict
```

## 3-Hour Sprint (推荐节奏)

- `0:00-0:30` Step 0：KDRoi Gate + 趋势初筛
- `0:30-1:30` Step 1-2：四路搜索 + 竞品差评挖掘
- `1:30-2:00` Step 3：ICP + 付费意愿验证
- `2:00-2:20` Step 4：TAM/SAM/SOM（Top-down + Bottom-up）
- `2:20-2:45` Step 5：定价与单位经济
- `2:45-3:00` Step 6：GO/NO-GO/HOLD + 30天动作

> 若超过 3 小时仍无法得到可验证证据，默认进入 `HOLD`，补充验证后再决策。

## Tooling Rules

- 浏览器优先级固定为 `ego-browser` -> `browser-skill` -> `@Chrome`；只有当前工具不可用或确认无法完成当前能力时才进入下一层，并记录失败信号。
- `ego-browser` 通过 `ego-browser nodejs`、同一 task space 和最终独立的 `completeTaskSpace(..., { keep: false })` 执行；`browser-skill` 必须完整执行 `bsk session start` -> 操作 -> `bsk session stop`；`@Chrome` 遵循 `chrome:control-chrome` 的 browser-client 工作流。
- 优先使用可复验公开来源：Google Trends、SimilarWeb、G2、Capterra、Trustpilot、Reddit、Product Hunt、Chrome Web Store、Statista、Crunchbase。
- 网页访问先走上述浏览器优先级；失败判定包括 403/429、验证码拦截、正文为空、关键字段缺失、强登录态阻塞。
- 触发兜底时必须记录：失败页面、失败信号、重试次数、下一层结果。
- Step 0 数据源优先级：
  - `weicoz-semrush-ego-browser` 生成的 Semrush Keyword Magic CSV/JSON（默认）
  - 已有 `Semrush / Ahrefs / Keyword Planner CSV`
  - `Google Ads Keyword Planner + 手工 SERP 难度`
  - `公开免费工具 proxy`（如 `kwresearch.io`）
- 只要任务需要真实 SEO `KD / Volume / CPC`，优先切到 `weicoz-semrush-ego-browser` 执行；不要手工编造 KD，也不要把 Google Ads competition 当作 SEO KD。
- 当拿不到真实 SEO `KD` 时，允许使用 `Ads-KDRoi proxy` 做预检，但输出中必须显式标注 `proxy`，不能伪装成标准 KDRoi。
- `proxy` 模式下，不允许仅凭 `Volume + CPC + Ads competition` 就把 `keyword_accessible=true` 判成强通过；必须追加 SERP 首页结构检查。

## Failure Branches

| 触发条件 | 处理动作 | 决策影响 |
|---|---|---|
| Semrush / Ahrefs / Keyword Planner 数据拿不到 | 改走 `Ads-KDRoi proxy`，并记录为 `eval_mode=proxy` | 只能进入 `pre-gate`，不得直接 `GO` |
| proxy 数据也拿不到 | 保留候选词，改用 SERP + Trends + 竞品证据做人工预检 | 默认 `HOLD` |
| KD > 29 但 Volume/CPC 很好 | 检查长尾词、替代词、模板词、比较词 | 原词 `HOLD/NO-GO`，长尾词可继续 |
| Volume < 200 但痛点强 | 检查宽词、替代搜索词、社区分发路径 | 默认 `HOLD`，不得靠低量词直接 `GO` |
| CPC = 0 或 WTP 证据缺失 | 补竞品价格、用户迁移、付费抱怨、替代方案成本 | 不得 `GO` |
| SERP 首页被巨头/官方/强品牌垄断 | 寻找更窄 wedge 或避开 SEO 分发 | 原方向 `NO-GO/HOLD` |
| 证据闸门失败 | 回到 Step 2/3 补证据 | 不得 `GO` |

🔴 CHECKPOINT: Step 0 结束时必须先给出 `Gate decision = PASS / HOLD / FAIL`。没有 Gate 结论，不进入完整 BRD。

## Workflow (Step 0 + Step 1-6)

### Step 0 - Demand Gate (KDRoi)

目标：快速判断关键词是否“可达 + 可变现”。

执行：
- 用 [references/roots-core.md](references/roots-core.md) 选 3-5 个词根扩展。
- 先调用 `weicoz-semrush-ego-browser` 获取第一页 Semrush Keyword Magic 结果，并保存到 `outputs/semrush-keywordmagic-page1.csv` / `.json`。
- 再跑 `rank_kdroi.py` 获取排序结果；如果 Semrush 脚本已产出 `kdroi`，仍允许用 `rank_kdroi.py` 做统一筛选和 Top N 截断。
- 对 Top 20 做四步验证：
  - 数据面（Volume/KD/CPC）
  - 趋势面（Google Trends）
  - 竞争面（SERP 首页结构）
  - 变现面（CPC/付费意图）
- 如果没有 SEO `KD`，改走 `Ads-KDRoi proxy`：
  - 用 `Volume x CPC(mid) / AdsCompetitionProxy` 排序
  - 再人工检查 SERP 首页是否被巨头、官方文档、超强品牌垄断
  - 最终只把它视作 `pre-gate`，不是最终 SEO 结论

默认通过门槛：
- `KD <= 29`
- `Volume >= 200`
- `CPC >= 0.1`
- 趋势平稳或上升
- SERP 非巨头完全垄断

Gate 输出必须包含：
- `keyword`
- `source = semrush / ahrefs / keyword_planner / proxy`
- `volume`
- `kd`
- `cpc`
- `kdroi`
- `trend`
- `serp_accessibility`
- `monetization_signal`
- `gate_decision`
- `reason`

Proxy 模式附加规则：
- `Ads-KDRoi proxy` 只用于排序与初筛，不单独决定 `GO`
- 优先保留：
  - `Volume >= 200`
  - `CPC >= 0.1`
  - `Ads competition != HIGH`
  - SERP 首页存在可切入结果（论坛、独立站、工具站、非巨头内容页）
- 如果精准词 `Volume` 极低，但宽词过宽，默认进入 `HOLD` 而不是强行 `GO`

产物：
- `outputs/semrush-keywordmagic-page1.csv`
- `outputs/semrush-keywordmagic-page1.json`
- `outputs/keywords-ranked.csv`
- `outputs/kdroi-gate.md`
- `outputs/ads-kdroi-proxy.csv`（仅在免费 / proxy 模式下）

### Step 1 - Demand Trend Gate

基于 Step 0 的通过词做趋势判断，输出方向、地区、语言。

执行要点：
- 主词至少看 `3y + 5y` 两个窗口。
- 必看 `Related Queries`，识别“总量小但增速快”的细分词。
- 若趋势下降，必须写明下降原因：需求萎缩 vs 被替代方案吞并。

### Step 2 - Competitor Pain Mining

跨平台挖痛点，要求可复现证据。

执行要点：
- 使用“四路搜索”采证：求助 / 吐槽 / 替代 / 交易。
- 竞品评论优先级：1-2 星差评 > `switched from A to B` > 3-4 星“差一点”评价。
- 只统计最近 `3-6` 个月证据，避免过时噪音。

### Step 3 - ICP & Willingness To Pay

锁定单一核心付费人群，明确可接受价格区间。

执行要点：
- 必须输出单一 ICP（名字/职业/场景/当前方案/月支出）。
- 必须给出“可接受价位区间”的证据来源（社区发言、评价、访谈记录）。

### Step 4 - Market Sizing

给出 TAM/SAM/SOM 和三档情景假设。

执行要点：
- Top-down：行业报告 + 增长率。
- Bottom-up：`月访问量 × 转化率 × 客单价` 反推。
- 至少给出保守 / 基准 / 乐观三档。

### Step 5 - Pricing & Unit Economics

输出可卖、可续费、可毛利的定价结构和回本逻辑。

执行要点：
- 先取竞品价格区间中位数，再做定位锚定（不是盲目比最低价）。
- 给出 Free / Pro / API 三层结构，说明额度与价格关系。
- 输出回本周期和毛利区间。

### Step 6 - Decision

按 scorecard 输出 `GO / NO-GO / HOLD`，并给 30 天计划。

Step 6 必须写清楚：
- 最终判断：`GO / NO-GO / HOLD`
- 最高置信证据 3 条
- 最大反证 3 条
- 30 天最小验证动作
- 若为 `HOLD`，下一步只补哪一个最关键证据

## Evidence Quality Gate（硬门槛）

- 同一痛点至少出现 `>=3` 次，且来自 `>=2` 平台，才算“真实痛点”。
- 至少 1 条“用户迁移证据”（如 `switched from ... to ...`）才算“可迁移市场”。
- 没有可验证付费意愿（WTP）证据时，不得判定 `GO`。
- 每条关键证据必须记录 `route / source_url / date_or_recency / quote_or_summary / confidence`。
- 如果证据来自 AI 总结而没有原始 URL 或可复查来源，只能作为线索，不能作为硬证据。

## Anti-Patterns

不要做：

- 不跑 Step 0，就直接写完整 BRD。
- 手工编造 KD、Volume、CPC。
- 把 Google Ads competition 或 `Ads-KDRoi proxy` 伪装成 SEO KD。
- 只凭高搜索量判定 `GO`。
- 只凭 Reddit 单个平台的几条吐槽判定“真实痛点”。
- 遇到旧报告排除方向时，把相似方向换个名字继续推荐。
- 输出泛泛“市场有机会”，但不给 ICP、WTP、竞品痛点、SERP 可达性。
- 证据闸门失败后继续强行给 `GO`。

## Output Protocol

- Goal
- Verify
- Next
- Blocker

最终产物必须落盘到工作区 `outputs/`：
- `semrush-keywordmagic-page1.csv` / `.json`（默认 KD 来源）
- `kdroi-gate.md`
- `BRD.md`
- `scoring-input.json`
- `market-research-report-YYYY-MM-DD-HHMMSS.md`（或主题命名）
- `evidence/evidence-log.csv`（必须含 route + recency + confidence）
- `outputs/evidence-gate-report.json`（证据闸门结果）
- `outputs/ads-kdroi-proxy.csv`（如果 Step 0 使用了免费 proxy）

## Resources

- [references/roots-core.md](references/roots-core.md): 词根清单。
- [references/query-pack.md](references/query-pack.md): 四路搜索包。
- [references/brd-template.md](references/brd-template.md): 融合版 BRD 模板。
- [references/go-no-go-scorecard.md](references/go-no-go-scorecard.md): 融合版评分卡。
- [references/report-template.md](references/report-template.md): Goal/Verify/Next/Blocker 报告模板。
- [references/scoring-input.example.json](references/scoring-input.example.json): 评分输入示例。
- [references/preflight-checklist.md](references/preflight-checklist.md): 10分钟预检清单。
- `scripts/init_research_workspace.sh`: 初始化工作区。
- `scripts/rank_kdroi.py`: KDRoi 排序脚本。
- `scripts/validate_evidence_gate.py`: 证据闸门脚本（可回填评分输入）。
- `scripts/score_go_no_go.py`: 决策建议脚本。
- `scripts/generate_brd_skeleton_from_evidence.py`: 根据证据日志生成 BRD 草稿。
- `scripts/run_fusion_pipeline.sh`: 一键执行 validate -> draft -> score。
- 免费 fallback：
  - `https://kwresearch.io/`
  - `https://www.semrush.com/free-tools/`
  - `https://ahrefs.com/free-seo-tools`
