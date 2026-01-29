#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # PyYAML
except Exception:
    yaml = None

def load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def load_yaml(p: str):
    if not p:
        return None
    if yaml is None:
        raise SystemExit("Missing dependency: pyyaml (pip install pyyaml)")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))

def get_delta_stats(delta: dict) -> dict:
    stats = (delta.get("stats") or {}) if isinstance(delta, dict) else {}
    add = int(stats.get("additions", 0) or 0)
    dele = int(stats.get("deletions", 0) or 0)
    churn = stats.get("churn_lines", None)
    if churn is None:
        churn = add + dele
    churn = int(churn or 0)
    files_changed = int(stats.get("files_changed", 0) or 0)
    return {"additions": add, "deletions": dele, "churn_lines": churn, "files_changed": files_changed}

def get_tests_signals(tests: dict) -> dict:
    # robusto: si faltan campos, intenta inferir
    exit_code = int(tests.get("exit_code", 0) or 0)
    duration_ms = int(tests.get("duration_ms", 0) or 0)

    tests_present = tests.get("tests_present", None)
    if tests_present is None:
        stderr = (tests.get("stderr") or "")
        tests_present = False if "tests skipped" in stderr.lower() else False
    tests_present = bool(tests_present)

    tests_passed = tests.get("tests_passed", None)
    if tests_passed is None:
        tests_passed = (exit_code == 0) and tests_present
    tests_passed = bool(tests_passed)

    return {"tests_present": tests_present, "tests_passed": tests_passed, "exit_code": exit_code, "duration_ms": duration_ms}

def get_sonar_signals(sonar: dict) -> dict:
    qg = (sonar.get("qualityGate") or {})
    qg_status = str(qg.get("status") or "NONE").upper()

    issues = sonar.get("issues_filtered_by_delta")
    if issues is None:
        issues = sonar.get("issues", []) or []

    sev_counts = {}
    for it in issues or []:
        sev = str(it.get("severity") or "UNKNOWN").upper()
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    return {"qg_status": qg_status, "sev_counts": sev_counts, "issues_in_delta": issues}

def infer_scope_from_policy(policy: dict | None) -> str:
    if not policy:
        return "unknown"
    meta = policy.get("meta") or {}
    scope = meta.get("scope") or policy.get("scope")
    return str(scope or "unknown").lower()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", required=True)
    ap.add_argument("--tests", required=True)
    ap.add_argument("--sonar", required=True)
    ap.add_argument("--policy", default=None, help="Optional policy YAML to infer scope/profile")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    delta = load_json(args.delta)
    tests = load_json(args.tests)
    sonar = load_json(args.sonar)
    policy = load_yaml(args.policy) if args.policy else None

    scope = infer_scope_from_policy(policy)
    if scope == "unknown":
        # fallback simple
        files = [f.get("path","") for f in (delta.get("files") or [])]
        files = [p for p in files if p]
        if files and all(p.startswith("qualityrisk/") or p == ".github/workflows/qualityrisk.yml" for p in files):
            scope = "tooling"
        else:
            scope = "web-static"

    is_tooling = (scope == "tooling")
    profile = "tooling-bootstrap" if is_tooling else "web-static-bootstrap"

    d = get_delta_stats(delta)
    t = get_tests_signals(tests)
    s = get_sonar_signals(sonar)

    score = 0
    reasons = []
    breakdown = {}

    def add(points: int, reason: str, key: str):
        nonlocal score
        if points <= 0:
            return
        score += points
        breakdown[key] = breakdown.get(key, 0) + points
        reasons.append(reason)

    # --- churn
    churn = d["churn_lines"]
    if churn >= 800:
        add(35 if not is_tooling else 25, f"High churn ({churn} lines)", "churn")
    elif churn >= 250:
        add(20 if not is_tooling else 12, f"Moderate-high churn ({churn} lines)", "churn")
    elif churn >= 100:
        add(10 if not is_tooling else 6, f"Moderate churn ({churn} lines)", "churn")

    # --- tests
    if not t["tests_present"]:
        add(25 if not is_tooling else 8, "No tests executed", "tests")
    elif not t["tests_passed"]:
        add(25 if not is_tooling else 12, "Tests failed", "tests")

    # --- quality gate
    if s["qg_status"] in ("ERROR", "FAIL"):
        add(25 if not is_tooling else 8, "Quality Gate failed", "quality_gate")

    # --- sonar issues in delta (severity-based)
    sev = s["sev_counts"]
    blockers = int(sev.get("BLOCKER", 0) or 0)
    criticals = int(sev.get("CRITICAL", 0) or 0)
    majors = int(sev.get("MAJOR", 0) or 0)

    if blockers:
        add(min(60, 40 * blockers), f"Sonar BLOCKER issues in delta: {blockers}", "sonar_blocker")
    if criticals:
        add(min(50, (25 if not is_tooling else 15) * criticals), f"Sonar CRITICAL issues in delta: {criticals}", "sonar_critical")
    if majors:
        add(min(30, 10 * majors), f"Sonar MAJOR issues in delta: {majors}", "sonar_major")

    score = clamp(int(score), 0, 100)

    if score >= 90:
        level = "CRITICAL"
    elif score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "qualityrisk.risk_score",
            "version": "2.0.0",
            "scope": scope,
            "profile": profile,
        },
        "value": score,
        "level": level,
        "reasons": reasons,
        "breakdown": breakdown,
        "signals": {
            "delta": d,
            "tests": t,
            "sonar": {"quality_gate": s["qg_status"], "sev_counts": sev},
        },
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
