#!/usr/bin/env python3
import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

API = "https://api.github.com"
DEFAULT_MARKER = "<!-- qualityrisk-report -->"

SEV_ORDER = {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3, "INFO": 4, "UNKNOWN": 9}


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_path(component: str) -> str:
    return component.split(":", 1)[1] if ":" in component else component


def gh_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "qualityrisk-pr-comment",
    }


def severity_counts(issues: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for it in issues or []:
        sev = (it.get("severity") or "UNKNOWN").upper()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def pick_delta_issues(evidence: dict) -> list[dict]:
    sonar = evidence.get("sonar") or {}
    delta_issues = sonar.get("issues_filtered_by_delta")
    if delta_issues is None:
        delta_issues = sonar.get("issues", []) or []
    return delta_issues or []


def issue_loc(issue: dict) -> str:
    path = extract_path(issue.get("component", ""))
    line = issue.get("line")
    if line is None:
        tr = issue.get("textRange") or {}
        line = tr.get("startLine")
    return f"{path}:{line}" if line else path


def sort_issues(issues: list[dict]) -> list[dict]:
    def key(it: dict):
        sev = (it.get("severity") or "UNKNOWN").upper()
        return (SEV_ORDER.get(sev, 9), str(it.get("rule") or ""), issue_loc(it))

    return sorted(issues or [], key=key)


def format_counts_md(counts: dict[str, int]) -> str:
    if not counts:
        return "- Sonar (delta issues): `none`"
    parts = [f"`{k}={v}`" for k, v in sorted(counts.items())]
    return "- Sonar (delta issues): " + ", ".join(parts)


def format_list_md(title: str, items: list[str], empty_msg: str) -> list[str]:
    lines = [f"### {title}"]
    if items:
        lines.extend([f"- {x}" for x in items])
    else:
        lines.append(f"- {empty_msg}")
    lines.append("")
    return lines


def format_violations_md(violations: list[dict]) -> list[str]:
    lines = ["### Policy violations"]
    if not violations:
        lines.append("- (none)")
        lines.append("")
        return lines

    for v in violations:
        status = v.get("status") or "WARN"
        rule_id = v.get("rule_id") or "unknown"
        reason = v.get("reason") or ""
        lines.append(f"- **{status}** `{rule_id}` — {reason}")
    lines.append("")
    return lines


def format_top_issues_md(delta_issues: list[dict], limit: int = 5) -> list[str]:
    if not delta_issues:
        return []

    top_lines = ["### Top Sonar issues in delta"]
    for it in sort_issues(delta_issues)[:limit]:
        sev = (it.get("severity") or "UNKNOWN").upper()
        loc = issue_loc(it)
        msg = (it.get("message") or "").strip()
        rule = it.get("rule") or ""
        top_lines.append(f"- **{sev}** `{loc}` — {msg} _(rule: `{rule}`)_")
    top_lines.append("")
    return top_lines


@dataclass
class Signals:
    repo: str
    pr: Any
    policy_set: str
    mode: str
    decision: str
    risk_value: int
    risk_level: str
    risk_reasons: list[str]
    qg: str
    files_changed: int
    additions: int
    deletions: int
    churn: int
    tests_present: bool
    tests_passed: bool
    exit_code: int
    duration_ms: int
    counts: dict[str, int]
    violations: list[dict]
    delta_issues: list[dict]
    generated_at: str


def extract_signals(evidence: dict) -> Signals:
    meta = evidence.get("meta") or {}
    delta = evidence.get("delta") or {}
    tests = evidence.get("tests") or {}
    sonar = evidence.get("sonar") or {}
    risk = evidence.get("risk") or {}
    policy = evidence.get("policy") or {}

    decision = (policy.get("decision") or "PASS").upper()
    policy_set = policy.get("policy_set") or "unknown"
    mode = (policy.get("mode") or "advisory").lower()

    qg = (sonar.get("qualityGate") or {}).get("status") or "NONE"
    qg = str(qg).upper()

    stats = delta.get("stats") or {}
    files_changed = int(stats.get("files_changed", 0) or 0)
    additions = int(stats.get("additions", 0) or 0)
    deletions = int(stats.get("deletions", 0) or 0)
    churn = int(stats.get("churn_lines", 0) or 0)

    tests_present = bool(tests.get("tests_present", False))
    tests_passed = bool(tests.get("tests_passed", False))
    exit_code = int(tests.get("exit_code", 0) or 0)
    duration_ms = int(tests.get("duration_ms", 0) or 0)

    delta_issues = pick_delta_issues(evidence)
    counts = severity_counts(delta_issues)
    violations = policy.get("violations") or []

    risk_value = int(risk.get("value", 0) or 0)
    risk_level = (risk.get("level") or "LOW").upper()
    risk_reasons = risk.get("reasons") or []

    return Signals(
        repo=str(meta.get("repo") or ""),
        pr=meta.get("pull_request"),
        policy_set=str(policy_set),
        mode=str(mode),
        decision=str(decision),
        risk_value=risk_value,
        risk_level=str(risk_level),
        risk_reasons=list(risk_reasons),
        qg=str(qg),
        files_changed=files_changed,
        additions=additions,
        deletions=deletions,
        churn=churn,
        tests_present=tests_present,
        tests_passed=tests_passed,
        exit_code=exit_code,
        duration_ms=duration_ms,
        counts=counts,
        violations=violations,
        delta_issues=delta_issues,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def build_markdown(evidence: dict, marker: str) -> str:
    s = extract_signals(evidence)

    lines: list[str] = []
    lines.append(f"## QualityRisk — `{s.policy_set}` ({s.mode})")
    lines.append("")
    lines.append(
        f"**Decision:** `{s.decision}`  |  **Risk:** `{s.risk_value}` (`{s.risk_level}`)  |  **Quality Gate:** `{s.qg}`"
    )
    lines.append("")
    lines.append("### Summary")
    lines.append(f"- Repo/PR: `{s.repo}` / `#{s.pr}`")
    lines.append(f"- Delta: **{s.files_changed} files**, **+{s.additions}/-{s.deletions}**, churn **{s.churn}**")
    lines.append(
        f"- Tests: present=`{s.tests_present}`, passed=`{s.tests_passed}`, exit_code=`{s.exit_code}`, duration_ms=`{s.duration_ms}`"
    )
    lines.append(format_counts_md(s.counts))
    lines.append("")

    # Risk reasons
    lines.extend(format_list_md("Risk reasons", s.risk_reasons, "(no reasons)"))

    # Policy violations
    lines.extend(format_violations_md(s.violations))

    # Top sonar issues
    lines.extend(format_top_issues_md(s.delta_issues, limit=5))

    lines.append(f"_generated_at: `{s.generated_at}`_")
    lines.append(marker)
    return "\n".join(lines)


def find_existing_comment(repo: str, pr: int, token: str, marker: str) -> Optional[int]:
    url = f"{API}/repos/{repo}/issues/{pr}/comments"
    headers = gh_headers(token)

    page = 1
    while True:
        r = requests.get(url, headers=headers, params={"per_page": 100, "page": page}, timeout=15)
        if r.status_code == 403:
            return None
        r.raise_for_status()
        items = r.json() or []
        for c in items:
            body = c.get("body") or ""
            if marker in body:
                return int(c.get("id"))
        if len(items) < 100:
            return None
        page += 1


def upsert_comment(repo: str, pr: int, token: str, body: str, marker: str) -> None:
    headers = gh_headers(token)
    existing_id = find_existing_comment(repo, pr, token, marker)

    if existing_id:
        url = f"{API}/repos/{repo}/issues/comments/{existing_id}"
        r = requests.patch(url, headers=headers, json={"body": body}, timeout=15)
        r.raise_for_status()
        print(f"Updated QualityRisk PR comment (id={existing_id})")
        return

    url = f"{API}/repos/{repo}/issues/{pr}/comments"
    r = requests.post(url, headers=headers, json={"body": body}, timeout=15)
    r.raise_for_status()
    print("Created QualityRisk PR comment")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--marker", default=DEFAULT_MARKER)
    ap.add_argument("--dry-run", action="store_true", help="Render only, do not post comment")
    args = ap.parse_args()

    evidence = load_json(args.evidence)
    md = build_markdown(evidence, args.marker)

    if args.out_md:
        with open(args.out_md, "w", encoding="utf-8") as f:
            f.write(md)

    print("Rendered QualityRisk report markdown.")

    if args.dry_run:
        return

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set; skipping PR comment.", file=sys.stderr)
        return

    try:
        upsert_comment(args.repo, args.pr, token, md, args.marker)
    except requests.HTTPError as e:
        # Best-effort: don't break pipeline if comment fails
        print(f"Failed to post PR comment: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
