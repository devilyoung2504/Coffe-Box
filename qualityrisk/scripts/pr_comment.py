#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

API = "https://api.github.com"
DEFAULT_MARKER = "<!-- qualityrisk-report -->"

def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_path(component: str) -> str:
    return component.split(":", 1)[1] if ":" in component else component

def severity_counts(issues: list[dict]) -> dict:
    counts = {}
    for it in issues or []:
        sev = (it.get("severity") or "UNKNOWN").upper()
        counts[sev] = counts.get(sev, 0) + 1
    return counts

def build_markdown(evidence: dict, marker: str) -> str:
    meta = evidence.get("meta") or {}
    delta = evidence.get("delta") or {}
    tests = evidence.get("tests") or {}
    sonar = evidence.get("sonar") or {}
    risk  = evidence.get("risk") or {}
    policy = evidence.get("policy") or {}

    # Headline signals
    decision = (policy.get("decision") or "PASS").upper()
    policy_set = policy.get("policy_set") or "unknown"
    mode = (policy.get("mode") or "advisory").lower()

    risk_value = int(risk.get("value", 0) or 0)
    risk_level = (risk.get("level") or "LOW").upper()
    reasons = risk.get("reasons") or []

    qg = (sonar.get("qualityGate") or {}).get("status") or "NONE"
    qg = str(qg).upper()

    # Delta stats
    stats = delta.get("stats") or {}
    files_changed = int(stats.get("files_changed", 0) or 0)
    additions = int(stats.get("additions", 0) or 0)
    deletions = int(stats.get("deletions", 0) or 0)
    churn = int(stats.get("churn_lines", 0) or 0)

    # Tests
    tests_present = bool(tests.get("tests_present", False))
    tests_passed = bool(tests.get("tests_passed", False))
    exit_code = int(tests.get("exit_code", 0) or 0)
    duration_ms = int(tests.get("duration_ms", 0) or 0)

    # Sonar delta issues
    delta_issues = sonar.get("issues_filtered_by_delta")
    if delta_issues is None:
        delta_issues = sonar.get("issues", []) or []
    counts = severity_counts(delta_issues)

    # Policy violations
    violations = policy.get("violations") or []

    # Top issues (max 5)
    top = []
    for it in (delta_issues or [])[:5]:
        path = extract_path(it.get("component", ""))
        line = it.get("line")
        tr = it.get("textRange") or {}
        if line is None:
            line = tr.get("startLine")
        sev = (it.get("severity") or "").upper()
        msg = (it.get("message") or "").strip()
        rule = it.get("rule") or ""
        loc = f"{path}:{line}" if line else path
        top.append(f"- **{sev}** `{loc}` — {msg} _(rule: `{rule}`)_")

    # Markdown
    generated = datetime.now(timezone.utc).isoformat()
    pr = meta.get("pull_request")
    repo = meta.get("repo")

    lines = []
    lines.append(f"## QualityRisk — `{policy_set}` ({mode})")
    lines.append("")
    lines.append(f"**Decision:** `{decision}`  |  **Risk:** `{risk_value}` (`{risk_level}`)  |  **Quality Gate:** `{qg}`")
    lines.append("")
    lines.append("### Summary")
    lines.append(f"- Repo/PR: `{repo}` / `#{pr}`")
    lines.append(f"- Delta: **{files_changed} files**, **+{additions}/-{deletions}**, churn **{churn}**")
    lines.append(f"- Tests: present=`{tests_present}`, passed=`{tests_passed}`, exit_code=`{exit_code}`, duration_ms=`{duration_ms}`")
    lines.append(f"- Sonar (delta issues): " + ", ".join([f"`{k}={v}`" for k, v in sorted(counts.items())]) if counts else "- Sonar (delta issues): `none`")
    lines.append("")
    lines.append("### Risk reasons")
    if reasons:
        for r in reasons:
            lines.append(f"- {r}")
    else:
        lines.append("- (no reasons)")
    lines.append("")
    lines.append("### Policy violations")
    if violations:
        for v in violations:
            lines.append(f"- **{v.get('status')}** `{v.get('rule_id')}` — {v.get('reason')}")
    else:
        lines.append("- (none)")
    lines.append("")
    if top:
        lines.append("### Top Sonar issues in delta")
        lines.extend(top)
        lines.append("")
    lines.append(f"_generated_at: `{generated}`_")
    lines.append(marker)
    return "\n".join(lines)

def gh_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "qualityrisk-pr-comment",
    }

def find_existing_comment(repo: str, pr: int, token: str, marker: str) -> int | None:
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

    # Always print a short line for logs
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
