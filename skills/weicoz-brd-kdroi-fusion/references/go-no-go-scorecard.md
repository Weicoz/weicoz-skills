# GO/NO-GO Scorecard (Fusion)

## GO Checks

- [ ] `keyword_accessible`: 至少 3 个关键词通过 KDRoi Gate（含趋势与 SERP 验证）。
- [ ] `validated_pain_points`: 至少 3 个真实痛点，且跨 >=2 平台验证。
- [ ] `clear_differentiation`: 明确切入点，且竞品短期内难快速补齐。
- [ ] `wtp_validated`: 有可验证付费意愿证据（价格讨论、交易页、或迁移付费线索）。
- [ ] `growing_demand`: 需求趋势稳定上升或强复苏。
- [ ] `startup_cost_under_500`: 启动成本在可承受范围（默认 < $500）。
- [ ] `payback_within_6_months`: 按保守模型 6 个月可回本。

## NO-GO Signals (>=2 建议 NO-GO)

- [ ] `no_accessible_keywords`: KDRoi Gate 后找不到可做关键词。
- [ ] `cannot_find_real_pain`: 找不到可重复验证的真实痛点。
- [ ] `competitors_are_free_and_sufficient`: 主流方案已免费且足够好。
- [ ] `demand_declining`: 需求长期下降且无替代性机会。
- [ ] `startup_cost_too_high`: 成本超预算且无明确回收路径。
- [ ] `no_distribution_channel`: 没有可执行获客路径。

## Decision Rule

1. NO-GO if NO-GO signals >= 2.
2. GO only if mandatory checks all pass:
   - `keyword_accessible`
   - `validated_pain_points`
   - `wtp_validated`
3. GO if mandatory checks pass and GO checks >= 4 and NO-GO signals < 2.
4. Otherwise HOLD and define additional validation experiments.
