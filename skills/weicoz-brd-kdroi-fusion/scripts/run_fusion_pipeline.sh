#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  run_fusion_pipeline.sh <workspace-dir> [--strict]

Examples:
  run_fusion_pipeline.sh ./ai-headshot-fusion-20260423-120000
  run_fusion_pipeline.sh ./ai-headshot-fusion-20260423-120000 --strict
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

workspace_dir="$1"
strict_flag="${2:-}"
if [[ -n "$strict_flag" && "$strict_flag" != "--strict" ]]; then
  echo "Error: only optional flag supported is --strict" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "$script_dir/.." && pwd)"

evidence_csv="$workspace_dir/evidence/evidence-log.csv"
scoring_json="$workspace_dir/outputs/scoring-input.json"
gate_report_json="$workspace_dir/outputs/evidence-gate-report.json"
brd_draft_md="$workspace_dir/outputs/BRD-draft-from-evidence.md"

if [[ ! -f "$evidence_csv" ]]; then
  echo "Error: evidence file not found: $evidence_csv" >&2
  exit 1
fi
if [[ ! -f "$scoring_json" ]]; then
  echo "Error: scoring file not found: $scoring_json" >&2
  exit 1
fi

echo "[1/3] Validate evidence gate..."
if [[ "$strict_flag" == "--strict" ]]; then
  python3 "$skill_root/scripts/validate_evidence_gate.py" \
    --evidence "$evidence_csv" \
    --scoring "$scoring_json" \
    --out "$gate_report_json" \
    --strict
else
  python3 "$skill_root/scripts/validate_evidence_gate.py" \
    --evidence "$evidence_csv" \
    --scoring "$scoring_json" \
    --out "$gate_report_json"
fi

echo "[2/3] Generate BRD auto draft..."
python3 "$skill_root/scripts/generate_brd_skeleton_from_evidence.py" \
  --evidence "$evidence_csv" \
  --out "$brd_draft_md"

echo "[3/3] Compute final decision..."
python3 "$skill_root/scripts/score_go_no_go.py" "$scoring_json"

echo
echo "DONE:"
echo "- gate_report: $gate_report_json"
echo "- brd_draft: $brd_draft_md"
echo "- scoring_input_updated: $scoring_json"
