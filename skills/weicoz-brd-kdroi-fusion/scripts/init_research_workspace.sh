#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  init_research_workspace.sh <project-slug> [output-dir]

Examples:
  init_research_workspace.sh ai-headshot-tool
  init_research_workspace.sh ai-headshot-tool ./research/ai-headshot-tool
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

slug="$1"
if [[ ! "$slug" =~ ^[a-z0-9-]+$ ]]; then
  echo "Error: <project-slug> must be hyphen-case (lowercase letters, digits, hyphens only)." >&2
  exit 1
fi

ts="$(date +%Y%m%d-%H%M%S)"
default_out="${WEICOZ_OUTPUT_ROOT:-$PWD}/${slug}-fusion-${ts}"
out_dir="${2:-$default_out}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "$script_dir/.." && pwd)"

mkdir -p "$out_dir/evidence" "$out_dir/notes" "$out_dir/outputs"

cp "$skill_root/references/evidence-log-template.csv" "$out_dir/evidence/evidence-log.csv"
cp "$skill_root/references/query-pack.md" "$out_dir/notes/query-pack.md"
cp "$skill_root/references/roots-core.md" "$out_dir/notes/roots-core.md"
cp "$skill_root/references/preflight-checklist.md" "$out_dir/notes/preflight-checklist.md"
cp "$skill_root/references/brd-template.md" "$out_dir/outputs/BRD.md"
cp "$skill_root/references/go-no-go-scorecard.md" "$out_dir/outputs/scorecard.md"

cat > "$out_dir/outputs/kdroi-gate.md" <<'MD'
# KDRoi Gate Report

## Goal
- 当前要验证的问题：
- 词根/关键词输入范围：

## Verify
- 筛选条件（KD/Volume/CPC）：
- 排序结果文件路径：
- Top 20 候选：
- 四步验证结果（数据/趋势/SERP/商业价值）：
- Gate 结论：GO / HOLD / NO-GO

## Next
- 下一步动作：

## Blocker
- 当前阻塞：
MD

cat > "$out_dir/outputs/scoring-input.json" <<JSON
{
  "go_checks": {
    "keyword_accessible": false,
    "validated_pain_points": false,
    "clear_differentiation": false,
    "wtp_validated": false,
    "growing_demand": false,
    "startup_cost_under_500": true,
    "payback_within_6_months": false
  },
  "no_go_signals": {
    "no_accessible_keywords": false,
    "cannot_find_real_pain": false,
    "competitors_are_free_and_sufficient": false,
    "demand_declining": false,
    "startup_cost_too_high": false,
    "no_distribution_channel": false
  },
  "notes": "Replace booleans after completing Step 0-6. GO requires keyword_accessible=true, validated_pain_points=true, and wtp_validated=true."
}
JSON

cat > "$out_dir/README.md" <<README
# BRD + KDRoi Fusion Workspace: ${slug}

## 1) Get Semrush KD data first via weicoz-semrush-bb-browser
\`\`\`bash
bb-browser open "https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmagic/?db=us&q=ai&filter=...&__gmitm=..." --tab
bb-browser site sem3ue/keywordmagic "<seed>" us <fid> --json --tab <tab-id>
\`\`\`

Only change the Semrush URL \`q\` parameter. Keep \`db=us\`, \`filter\`, and \`__gmitm\` intact.

## 2) KDRoi Gate
\`\`\`bash
python3 "$skill_root/scripts/rank_kdroi.py" \\
  --in "$out_dir/outputs/semrush-keywordmagic-page1.csv" \\
  --out "$out_dir/outputs/keywords-ranked.csv" \\
  --min-kd 0 --max-kd 29 \\
  --min-volume 200 --max-volume 10000 \\
  --min-cpc 0.1 --top 20
\`\`\`

填完：
- outputs/kdroi-gate.md

## 3) Run BRD Step 1-6
- outputs/BRD.md
- evidence/evidence-log.csv
- outputs/scorecard.md

## 4) Validate evidence gate
\`\`\`bash
python3 "$skill_root/scripts/validate_evidence_gate.py" \\
  --evidence "$out_dir/evidence/evidence-log.csv" \\
  --scoring "$out_dir/outputs/scoring-input.json" \\
  --out "$out_dir/outputs/evidence-gate-report.json"
\`\`\`

## 5) Compute decision
\`\`\`bash
python3 "$skill_root/scripts/score_go_no_go.py" "$out_dir/outputs/scoring-input.json"
\`\`\`

## 6) Generate BRD auto draft (optional)
\`\`\`bash
python3 "$skill_root/scripts/generate_brd_skeleton_from_evidence.py" \\
  --evidence "$out_dir/evidence/evidence-log.csv" \\
  --out "$out_dir/outputs/BRD-draft-from-evidence.md"
\`\`\`

## 7) One command pipeline (optional)
\`\`\`bash
"$skill_root/scripts/run_fusion_pipeline.sh" "$out_dir"
# strict mode:
"$skill_root/scripts/run_fusion_pipeline.sh" "$out_dir" --strict
\`\`\`

## 8) Final output
在 outputs/ 下新增最终报告：
- market-research-report-YYYY-MM-DD-HHMMSS.md
或
- <topic-slug>-YYYY-MM-DD-HHMMSS.md
README

echo "Workspace created: $out_dir"
echo "Next: run KDRoi gate, then complete BRD."
