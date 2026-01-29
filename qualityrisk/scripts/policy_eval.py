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
    # delta.files_changed
    # tests.tests_present
    # sonar.quality_gate_status
    parts = key.split(".")
    root = parts[0]

    if root == "delta":
        stats = (evidence.get("delta") or {}).get("stats", {}) or {}
        if len(parts) > 1 and parts[1] == "churn_lines":
            return int(stats.get("churn_lines", 0) or 0)
        if len(parts) > 1 and parts[1] == "files_changed":
            return int(stats.get("files_changed", 0) or 0)

    if root == "tests":
        t = evidence.get("tests") or {}
        if len(parts) > 1 and parts[1] == "tests_present":
            return bool(t.get("tests_present", False))
        if len(parts) > 1 and parts[1] == "tests_passed":
            return bool(t.get("tests_passed", False))
        if len(parts) > 1 and parts[1] == "exit_code":
            return int(t.get("exit_code", 0) or 0)

    if root == "sonar":
        s = evidence.get("sonar") or {}
        if len(parts) > 1 and parts[1] == "quality_gate_status":
            qg = (s.get("qualityGate") or {})
            return (qg.get("status") or "NONE").upper()

    if root == "risk":
        if len(parts) > 1 and parts[1] == "value":
            return int(risk.get("value", 0) or 0)
        if len(parts) > 1 and parts[1] == "level":
            return (risk.get("level") or "LOW").upper()

    return None


def count_delta_issues_by_sev(evidence: dict, severities: list[str]) -> int:
    s = evidence.get("sonar") or {}
    issues = s.get("issues_filtered_by_delta")
    if issues is None:
        issues = s.get("issues", []) or []
    sevset = {x.upper() for x in severities}
    return sum(1 for it in issues if (it.get("severity") or "").upper() in sevset)


def _eval_threshold_rule(
    actual,
    warn_gte: int,
    block_gte: int,
    on_fail: str,
    reason_warn: str,
    reason_block: str,
    reason_ok: str,
):
    # Normaliza None -> 0 para reglas numéricas
    try:
        actual_num = int(actual or 0)
    except Exception:
        actual_num = 0

    if actual_num >= block_gte:
        return "BLOCK", reason_block.format(actual=actual_num, block_gte=block_gte), actual_num
    if actual_num >= warn_gte:
        return on_fail, reason_warn.format(actual=actual_num, warn_gte=warn_gte), actual_num
    return "PASS", reason_ok.format(actual=actual_num), actual_num


# -----------------------
# Handlers por rule type
# -----------------------
def handle_quality_gate_status(evidence: dict, risk: dict, rule: dict):
    actual = get_signal(evidence, risk, "sonar.quality_gate_status")
    expect = (rule.get("expect") or "OK").upper()
    if (actual or "NONE").upper() != expect:
        status = rule.get("on_fail", "BLOCK")
        return status, f"Quality Gate status is {actual} (expected {expect})", actual
    return "PASS", "Quality Gate passed", actual


def handle_tests_present(evidence: dict, risk: dict, rule: dict):
    actual = get_signal(evidence, risk, "tests.tests_present")
    expect = bool(rule.get("expect", True))
    if bool(actual) != expect:
        status = rule.get("on_fail", "WARN")
        return status, "No tests executed", actual
    return "PASS", "Tests executed", actual


def handle_delta_churn(evidence: dict, risk: dict, rule: dict):
    actual = get_signal(evidence, risk, "delta.churn_lines")
    warn_gte = int(rule.get("warn_gte", 10**9))
    block_gte = int(rule.get("block_gte", 10**9))
    on_fail = rule.get("on_fail", "WARN")
    return _eval_threshold_rule(
        actual,
        warn_gte,
        block_gte,
        on_fail,
        reason_warn="High churn ({actual} >= {warn_gte})",
        reason_block="Churn too high ({actual} >= {block_gte})",
        reason_ok="Churn OK ({actual})",
    )


def handle_risk_value(evidence: dict, risk: dict, rule: dict):
    actual = get_signal(evidence, risk, "risk.value")
    warn_gte = int(rule.get("warn_gte", 10**9))
    block_gte = int(rule.get("block_gte", 10**9))
    on_fail = rule.get("on_fail", "WARN")
    return _eval_threshold_rule(
        actual,
        warn_gte,
        block_gte,
        on_fail,
        reason_warn="Risk score high ({actual} >= {warn_gte})",
        reason_block="Risk score too high ({actual} >= {block_gte})",
        reason_ok="Risk score OK ({actual})",
    )


def handle_delta_issues_sev_count(evidence: dict, risk: dict, rule: dict):
    sevs = rule.get("severities") or []
    max_allowed = int(rule.get("max", 0))
    actual = count_delta_issues_by_sev(evidence, sevs)
    if actual > max_allowed:
        status = rule.get("on_fail", "BLOCK")
        return status, f"Delta issues in {sevs}: {actual} > {max_allowed}", actual
    return "PASS", f"Delta issues in {sevs}: {actual} <= {max_allowed}", actual


def handle_files_changed(evidence: dict, risk: dict, rule: dict):
    actual = get_signal(evidence, risk, "delta.files_changed")
    warn_gte = int(rule.get("warn_gte", 10**9))
    block_gte = int(rule.get("block_gte", 10**9))
    on_fail = rule.get("on_fail", "WARN")
    return _eval_threshold_rule(
        actual,
        warn_gte,
        block_gte,
        on_fail,
        reason_warn="Many files changed ({actual} >= {warn_gte})",
        reason_block="Too many files changed ({actual} >= {block_gte})",
        reason_ok="Files changed OK ({actual})",
    )


HANDLERS = {
    "sonar.quality_gate_status": handle_quality_gate_status,
    "tests.tests_present": handle_tests_present,
    "delta.churn_lines": handle_delta_churn,
    "risk.value": handle_risk_value,
    "sonar.delta_issues_severity_count": handle_delta_issues_sev_count,
    "delta.files_changed": handle_files_changed,
}


def eval_rule(evidence: dict, risk: dict, rule: dict):
    rid = rule["id"]
    rtype = rule["type"]

    handler = HANDLERS.get(rtype)
    if handler is None:
        status, reason, actual = "WARN", f"Unknown rule type: {rtype}", None
    else:
        status, reason, actual = handler(evidence, risk, rule)

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
            violations.append(
                {"rule_id": ev["rule_id"], "status": ev["status"], "reason": ev["reason"]}
            )

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "qualityrisk.policy_eval",
            "version": "1.0.1",
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
