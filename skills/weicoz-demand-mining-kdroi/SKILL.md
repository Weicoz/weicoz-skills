---
name: weicoz-demand-mining-kdroi
version: 1.0.0
description: 基于 KDRoi（搜索量 x CPC / KD）执行出海工具站需求挖掘与四步验证。用于“选需求/选关键词/判断值不值得做”，目标是降低选错需求的概率并输出可直接执行的候选方向。
---

# Demand Mining KDRoi

## Goal

把“凭感觉选需求”改成“数据驱动选需求”。  
输出结果不是泛泛建议，而是可执行的关键词候选清单和验证结论。

## Inputs

- 至少 1 个词根（如 `generator`、`calculator`）。
- 关键词来源数据（Semrush CSV 或 Google Ads Keyword Planner 导出 CSV）。
- 可选：1-3 个竞品域名（用于“站找词/站找站”）。

## Quick Start

1. 导出关键词 CSV（建议先用以下筛选）：
   - `KD: 0-29`
   - `Volume: 200-10000`
   - `CPC: >= 0.1`
   - 排除包含 `near me` 的词
2. 运行排序脚本：
```bash
python3 scripts/rank_kdroi.py \
  --in /path/to/keywords.csv \
  --out /path/to/keywords_ranked.csv \
  --min-kd 0 --max-kd 29 \
  --min-volume 200 --max-volume 10000 \
  --min-cpc 0.1
```
3. 取 Top 20 候选，执行“四步验证”。
4. 只保留验证通过的需求进入建站阶段。

## Workflow

### Step 1 - 词根扩展（新手优先）

优先读取 [references/roots-core.md](references/roots-core.md) 里的核心词根。  
先跑 3-5 个词根，避免一次性铺太开。

### Step 2 - KDRoi 初筛（核心）

公式：

`KDRoi = Volume x CPC / KD`

解释：
- `Volume` 代表需求大小。
- `CPC` 代表商业价值。
- `KD` 代表竞争强度。

规则：
- 新站优先 `KD < 30`。
- `CPC < 0.1` 默认低优先级。
- 不追“大词幻觉”，按 KDRoi 先后排序。

### Step 3 - 四步验证（必须）

对每个候选关键词依次检查：

1. `Semrush/Keyword Planner`：确认 Volume、KD、CPC 基础面成立。
2. `Google Trends`：趋势是否稳定或上升，避免强季节性陷阱。
3. `Google SERP`：首页是否被超强站点垄断（如维基/亚马逊/超强老站）。
4. `商业价值`：CPC 是否足够支撑变现（广告、订阅、工具付费）。

通过门槛（默认）：
- `KD <= 29`
- `Volume >= 200`
- `CPC >= 0.1`
- 趋势平稳/上升
- SERP 非巨头完全垄断

### Step 4 - 决策分层

- `GO`：全部通过，立即进入 MVP。
- `HOLD`：有潜力但缺 1-2 条关键证据（先补验证）。
- `NO-GO`：KD 过高、CPC 过低或趋势明显下滑。

## 8 Ways To Find Demands（由易到难）

1. 词根扩展（Generator/Converter/Calculator...）
2. 竞品出站链接反查需求
3. 支付网关反查（优先看已变现站点）
4. 词找词 -> 站找词 -> 站找站 循环
5. 社媒热点追踪（X/Reddit/TikTok）
6. Chrome 插件差评挖痛点
7. AI 导航站请求页（用户主动需求）
8. Vercel 子域名/新站生态观察

## Anti-Patterns

- 只看搜索量，不看 KD 和 CPC。
- 不做验证直接建站。
- 迷信“大词”，忽略新站可达性。
- 只靠直觉判断，不保留数据证据。

## Output Protocol

按下面结构输出每次结果（必要时保存为 Markdown 文件）：

- `Goal`: 本轮要验证的问题。
- `Verify`: 数据事实、来源、是否达标。
- `Next`: 下一步动作（可执行）。
- `Blocker`: 超过一个工作时段无法推进时必须声明。

可直接使用模板：
[references/report-template.md](references/report-template.md)
