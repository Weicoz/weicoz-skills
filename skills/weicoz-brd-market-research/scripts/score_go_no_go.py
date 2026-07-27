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


def recommend(go_count: int, no_go_count: int):
    if no_go_count >= 2:
        return "NO-GO"
    if go_count >= 3:
        return "GO"
    return "HOLD"


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
    decision = recommend(go_count, no_go_count)

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
    print("- NO-GO if NO-GO signals >= 2")
    print("- GO if GO checks >= 3 and NO-GO signals < 2")
    print("- Otherwise HOLD")


if __name__ == "__main__":
    main()
