#!/usr/bin/env python3
"""Compute GO/NO-GO/HOLD recommendation from BRD checks."""

import json
import sys
from pathlib import Path


def load_payload(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    go_checks = data.get("go_checks", {})
    no_go_signals = data.get("no_go_signals", {})
    if not isinstance(go_checks, dict) or not isinstance(no_go_signals, dict):
        raise ValueError("go_checks and no_go_signals must be JSON objects")
    return go_checks, no_go_signals


def bool_count(mapping):
    true_keys = [k for k, v in mapping.items() if bool(v) is True]
    return len(true_keys), true_keys


GO_THRESHOLD = 4
NO_GO_THRESHOLD = 2
MANDATORY_GO_KEYS = ("keyword_accessible", "validated_pain_points", "wtp_validated")


def recommend(go_checks, no_go_signals):
    go_count, _ = bool_count(go_checks)
    no_go_count, _ = bool_count(no_go_signals)
    missing_mandatory = [k for k in MANDATORY_GO_KEYS if bool(go_checks.get(k)) is not True]
    if no_go_count >= NO_GO_THRESHOLD:
        return "NO-GO", missing_mandatory
    if not missing_mandatory and go_count >= GO_THRESHOLD:
        return "GO", missing_mandatory
    return "HOLD", missing_mandatory


def main():
    if len(sys.argv) != 2:
        print("Usage: score_go_no_go.py <scoring-input.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1]).resolve()
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    try:
        go_checks, no_go_signals = load_payload(input_path)
    except Exception as exc:
        print(f"Error: invalid input: {exc}")
        sys.exit(1)

    go_count, go_true = bool_count(go_checks)
    no_go_count, no_go_true = bool_count(no_go_signals)
    decision, missing_mandatory = recommend(go_checks, no_go_signals)

    print("# BRD Decision Summary")
    print(f"Decision: {decision}")
    print(f"GO checks passed: {go_count}/{len(go_checks)}")
    print(f"NO-GO signals hit: {no_go_count}/{len(no_go_signals)}")

    print("\nGO checks = true:")
    if go_true:
        for key in go_true:
            print(f"- {key}")
    else:
        print("- (none)")

    print("\nNO-GO signals = true:")
    if no_go_true:
        for key in no_go_true:
            print(f"- {key}")
    else:
        print("- (none)")

    print("\nRule:")
    print(f"- NO-GO if NO-GO signals >= {NO_GO_THRESHOLD}")
    print(f"- Mandatory GO checks: {', '.join(MANDATORY_GO_KEYS)}")
    if missing_mandatory:
        print(f"- Missing mandatory checks now: {', '.join(missing_mandatory)}")
    else:
        print("- Missing mandatory checks now: (none)")
    print(f"- GO if mandatory checks pass and GO checks >= {GO_THRESHOLD} and NO-GO signals < {NO_GO_THRESHOLD}")
    print("- Otherwise HOLD")


if __name__ == "__main__":
    main()
