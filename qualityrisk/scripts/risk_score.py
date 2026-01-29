#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone

SEVERITY_POINTS = {
    "BLOCKER": 30,
    "CRITICAL": 20,
    "MAJOR": 8,
    "MINOR": 2,
    "INFO": 1,
}

SEVERITY_CAP = {
    "BLOCKER": 60,
    "CRITICAL": 60,
    "MAJOR": 40,
    "MINOR": 10,
    "INFO": 5,
}

def load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))

def level_for(score: int) -> str:
    # Ajustable a gusto
    if score >= 80:
        return "CRITICAL"
    if score >= 55:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"

def count_by_severity(issues: list[dict]) -> dict[str, int]:
    out = {"BLOCKER": 0, "CRITICAL": 0, "MAJOR": 0, "MINOR": 0, "INFO": 0}
    for it in issues or []:
        sev = (it.get("severity") or "").upper()
        if sev in out:
            out[sev] += 1
    return out

def add_breakdown(breakdown: list, reasons: list, rule_id: str, points: int, reason: str):
    if points <= 0:
        return 0
    breakdown.append({"rule_id": rule_id, "points": points, "reason": reason})
    reasons.append(reason)
    return points

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", required=True)
    ap.add_argument("--tests", required=True)
    ap.add_argument("--sonar", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    delta = load(args.delta)
    tests = load(args.tests)
    sonar = load(args.sonar)

    breakdown = []
    reasons = []
    score = 0

    # ---- Delta signals
    stats = (delta or {}).get("stats", {}) or {}
    churn = int(stats.get("churn_lines", 0) or 0)
    files_changed = int(stats.get("files_changed", 0) or 0)
    additions = int(stats.get("additions", 0) or stats.get("total_additions", 0) or 0)
    deletions = int(stats.get("deletions", 0) or stats.get("total_deletions", 0) or 0)

    if churn > 500:
        score += add_breakdown(breakdown, reasons, "delta.churn", 20, f"High code churn ({churn} lines)")
    elif churn > 200:
        score += add_breakdown(breakdown, reasons, "delta.churn", 12, f"Moderate-high churn ({churn} lines)")
    elif churn > 80:
        score += add_breakdown(breakdown, reasons, "delta.churn", 6, f"Moderate churn ({churn} lines)")

    if files_changed > 30:
        score += add_breakdown(breakdown, reasons, "delta.files_changed", 10, f"Many files changed ({files_changed})")
    elif files_changed > 15:
        score += add_breakdown(breakdown, reasons, "delta.files_changed", 6, f"Several files changed ({files_changed})")
    elif files_changed > 5:
        score += add_breakdown(breakdown, reasons, "delta.files_changed", 3, f"Multiple files changed ({files_changed})")

    # ---- Tests signals
    tests_present = bool((tests or {}).get("tests_present", False))
    tests_passed = bool((tests or {}).get("tests_passed", False))
    exit_code = int((tests or {}).get("exit_code", 0) or 0)

    if not tests_present:
        score += add_breakdown(breakdown, reasons, "tests.present", 30, "No tests executed")
    elif not tests_passed or exit_code != 0:
        score += add_breakdown(breakdown, reasons, "tests.passed", 40, "Tests failed")

    # ---- Sonar signals
    qg = (sonar or {}).get("qualityGate", {}) or {}
    qg_status = (qg.get("status") or "NONE").upper()

    if qg_status == "ERROR":
        score += add_breakdown(breakdown, reasons, "sonar.quality_gate", 35, "Quality Gate failed")
    elif qg_status == "NONE":
        score += add_breakdown(breakdown, reasons, "sonar.quality_gate", 15, "Quality Gate not ready (NONE)")
    # OK => 0

    # Prefer issues already filtered by delta (tu sonar_fetch.py los produce)
    delta_issues = (sonar or {}).get("issues_filtered_by_delta")
    if delta_issues is None:
        delta_issues = (sonar or {}).get("issues", []) or []

    sev_counts = count_by_severity(delta_issues)

    # Score by severity with caps (determinístico y audit)
    for sev, cnt in sev_counts.items():
        if cnt <= 0:
            continue
        points = min(cnt * SEVERITY_POINTS[sev], SEVERITY_CAP[sev])
        score += add_breakdown(
            breakdown, reasons,
            f"sonar.issues.{sev.lower()}",
            points,
            f"Sonar {sev} issues in delta: {cnt}"
        )

    score = clamp(score)
    level = level_for(score)

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "qualityrisk.risk_score",
            "version": "1.0.0",
        },
        "value": score,
        "level": level,
        "reasons": reasons,
        "signals": {
            "delta": {
                "files_changed": files_changed,
                "additions": additions,
                "deletions": deletions,
                "churn_lines": churn,
            },
            "tests": {
                "tests_present": tests_present,
                "tests_passed": tests_passed,
                "exit_code": exit_code,
            },
            "sonar": {
                "quality_gate_status": qg_status,
                "delta_issue_counts": sev_counts,
                "delta_issue_total": len(delta_issues or []),
            },
        },
        "breakdown": breakdown,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
