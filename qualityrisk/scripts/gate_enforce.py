#!/usr/bin/env python3
import argparse
import json
import sys

def load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-result", required=True)
    args = ap.parse_args()

    pr = load_json(args.policy_result)
    mode = str(pr.get("mode") or "advisory").lower()
    decision = str(pr.get("decision") or "PASS").upper()

    print(f"Policy mode={mode} decision={decision}")

    if mode == "enforcing" and decision == "BLOCK":
        print("QualityRisk gate: BLOCK (enforcing) -> failing job.")
        sys.exit(1)

    print("QualityRisk gate: OK (or advisory).")
    sys.exit(0)

if __name__ == "__main__":
    main()
