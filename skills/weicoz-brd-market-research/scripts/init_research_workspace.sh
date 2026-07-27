#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  init_research_workspace.sh <project-slug> [output-dir]

Examples:
  init_research_workspace.sh product-photo-bg
  init_research_workspace.sh product-photo-bg ./research/product-photo-bg
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
default_out="$PWD/${slug}-brd-${ts}"
out_dir="${2:-$default_out}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "$script_dir/.." && pwd)"

mkdir -p "$out_dir/evidence" "$out_dir/notes" "$out_dir/outputs"

cp "$skill_root/references/evidence-log-template.csv" "$out_dir/evidence/evidence-log.csv"
cp "$skill_root/references/query-pack.md" "$out_dir/notes/query-pack.md"
cp "$skill_root/references/brd-template.md" "$out_dir/outputs/BRD.md"
cp "$skill_root/references/go-no-go-scorecard.md" "$out_dir/outputs/scorecard.md"

cat > "$out_dir/outputs/scoring-input.json" <<JSON
{
  "go_checks": {
    "validated_pain_points": false,
    "clear_differentiation": false,
    "growing_demand": false,
    "startup_cost_under_500": true,
    "payback_within_6_months": false
  },
  "no_go_signals": {
    "cannot_find_real_pain": false,
    "competitors_are_free_and_sufficient": false,
    "demand_declining": false,
    "startup_cost_too_high": false,
    "no_distribution_channel": false
  },
  "notes": "Replace booleans after completing BRD research."
}
JSON

cat > "$out_dir/README.md" <<README
# BRD Research Workspace: ${slug}

## 1) Run the 6-step workflow
- Start from:
  - outputs/BRD.md
  - outputs/scorecard.md
  - evidence/evidence-log.csv

## 2) Fill scoring input and compute recommendation
\`\`\`bash
python3 "$skill_root/scripts/score_go_no_go.py" "$out_dir/outputs/scoring-input.json"
\`\`\`

## 3) Decision rule
- NO-GO if >=2 no-go signals are true.
- GO if >=3 go checks are true and no-go signals <2.
- Otherwise HOLD and define additional validation experiments.
README

echo "Workspace created: $out_dir"
echo "Next: fill evidence/evidence-log.csv and outputs/BRD.md"
