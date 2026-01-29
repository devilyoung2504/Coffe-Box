#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # PyYAML
except Exception:
    yaml = None

ORDER = {"PASS": 0, "WARN": 1, "BLOCK": 2}

def load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def load_yaml(p: str):
    if yaml is None:
        raise SystemExit("Missing dependency: pyyaml (pip install pyyaml)")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def decision_max(a: str, b: str) -> str:
    return a if ORDER[a] >= ORDER[b] else b

def get_signal(evidence: dict, risk: dict, key: str):
    # key examples:
    # delta.churn_lines
    # tests.tests_present
    # sonar.quality_gate_status
    parts = key.split(".")
    root = parts[0]

    if root == "delta":
        stats = (evidence.get("delta") or {}).get("stats", {}) or {}
        if parts[1] == "churn_lines":
            return int(stats.get("churn_lines", 0) or 0)
        if parts[1] == "files_changed":
            return int(stats.get("files_changed", 0) or 0)

    if root == "tests":
        t = evidence.get("tests") or {}
        if parts[1] == "tests_present":
            return bool(t.get("tests_present", False))
        if parts[1] == "tests_passed":
            return bool(t.get("tests_passed", False))
        if parts[1] == "exit_code":
            return int(t.get("exit_code", 0) or 0)

    if root == "sonar":
        s = evidence.get("sonar") or {}
        if parts[1] == "quality_gate_status":
            qg = (s.get("qualityGate") or {})
            return (qg.get("status") or "NONE").upper()

    if root == "risk":
        if parts[1] == "value":
            return int(risk.get("value", 0) or 0)
        if parts[1] == "level":
            return (risk.get("level") or "LOW").upper()

    return None

def count_delta_issues_by_sev(evidence: dict, severities: list[str]) -> int:
    s = evidence.get("sonar") or {}
    issues = s.get("issues_filtered_by_delta")
    if issues is None:
        issues = s.get("issues", []) or []
    sevset = {x.upper() for x in severities}
    cnt = 0
    for it in issues:
        if (it.get("severity") or "").upper() in sevset:
            cnt += 1
    return cnt

def eval_rule(evidence: dict, risk: dict, rule: dict):
    rid = rule["id"]
    rtype = rule["type"]

    # default
    status = "PASS"
    reason = ""
    actual = None

    if rtype == "sonar.quality_gate_status":
        actual = get_signal(evidence, risk, "sonar.quality_gate_status")
        expect = (rule.get("expect") or "OK").upper()
        if actual != expect:
            status = rule.get("on_fail", "BLOCK")
            reason = f"Quality Gate status is {actual} (expected {expect})"
        else:
            reason = "Quality Gate passed"

    elif rtype == "tests.tests_present":
        actual = get_signal(evidence, risk, "tests.tests_present")
        expect = bool(rule.get("expect", True))
        if actual != expect:
            status = rule.get("on_fail", "WARN")
            reason = "No tests executed"
        else:
            reason = "Tests executed"

    elif rtype == "delta.churn_lines":
        actual = get_signal(evidence, risk, "delta.churn_lines")
        warn_gte = int(rule.get("warn_gte", 10**9))
        block_gte = int(rule.get("block_gte", 10**9))
        if actual >= block_gte:
            status = "BLOCK"
            reason = f"Churn too high ({actual} >= {block_gte})"
        elif actual >= warn_gte:
            status = rule.get("on_fail", "WARN")
            reason = f"High churn ({actual} >= {warn_gte})"
        else:
            reason = f"Churn OK ({actual})"

    elif rtype == "risk.value":
        actual = get_signal(evidence, risk, "risk.value")
        warn_gte = int(rule.get("warn_gte", 10**9))
        block_gte = int(rule.get("block_gte", 10**9))
        if actual >= block_gte:
            status = "BLOCK"
            reason = f"Risk score too high ({actual} >= {block_gte})"
        elif actual >= warn_gte:
            status = rule.get("on_fail", "WARN")
            reason = f"Risk score high ({actual} >= {warn_gte})"
        else:
            reason = f"Risk score OK ({actual})"

    elif rtype == "sonar.delta_issues_severity_count":
        sevs = rule.get("severities") or []
        max_allowed = int(rule.get("max", 0))
        actual = count_delta_issues_by_sev(evidence, sevs)
        if actual > max_allowed:
            status = rule.get("on_fail", "BLOCK")
            reason = f"Delta issues in {sevs}: {actual} > {max_allowed}"
        else:
            reason = f"Delta issues in {sevs}: {actual} <= {max_allowed}"

    elif rtype == "delta.files_changed":
        actual = get_signal(evidence, risk, "delta.files_changed")
        warn_gte = int(rule.get("warn_gte", 10**9))
        block_gte = int(rule.get("block_gte", 10**9))

        if actual >= block_gte:
            status = "BLOCK"
            reason = f"Too many files changed ({actual} >= {block_gte})"
        elif actual >= warn_gte:
            status = rule.get("on_fail", "WARN")
            reason = f"Many files changed ({actual} >= {warn_gte})"
        else:
            reason = f"Files changed OK ({actual})"
        

    else:
        status = "WARN"
        reason = f"Unknown rule type: {rtype}"

    return {
        "rule_id": rid,
        "type": rtype,
        "status": status,
        "actual": actual,
        "reason": reason,
        "config": rule,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--risk", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    evidence = load_json(args.evidence)
    risk = load_json(args.risk)

    policy = load_yaml(args.policy)
    rules = policy.get("rules", [])

    evaluations = []
    decision = "PASS"
    violations = []

    for r in rules:
        ev = eval_rule(evidence, risk, r)
        evaluations.append(ev)
        decision = decision_max(decision, ev["status"])
        if ev["status"] in ("WARN", "BLOCK"):
            violations.append({"rule_id": ev["rule_id"], "status": ev["status"], "reason": ev["reason"]})

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "qualityrisk.policy_eval",
            "version": "1.0.0",
        },
        "policy_set": policy.get("policy_set", "unknown"),
        "mode": policy.get("mode", "advisory"),
        "decision": decision,
        "violations": violations,
        "evaluations": evaluations,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
