#!/usr/bin/env python3
import argparse
import json
import os
import requests
import time
from datetime import datetime, timezone

SONAR_HOST = "https://sonarcloud.io"

def sonar_get(path: str, token: str, params: dict):
    url = f"{SONAR_HOST}{path}"
    r = requests.get(url, params=params, auth=(token, ""))
    r.raise_for_status()
    return r.json()

def wait_for_pr_analysis(token: str, project_key: str, pr: str, timeout_s: int = 90, sleep_s: int = 3):
    start = time.time()
    deadline = start + timeout_s
    last = None
    while time.time() < deadline:
        qg = sonar_get(
            "/api/qualitygates/project_status",
            token,
            {"projectKey": project_key, "pullRequest": pr},
        )
        status = (qg.get("projectStatus") or {}).get("status")
        last = qg
        if status and status != "NONE":
            return qg, {"timed_out": False, "elapsed_s": round(time.time() - start, 2), "timeout_s": timeout_s, "sleep_s": sleep_s}
        time.sleep(sleep_s)
    return last, {"timed_out": True, "elapsed_s": round(time.time() - start, 2), "timeout_s": timeout_s, "sleep_s": sleep_s}

def extract_path(component: str) -> str:
    return component.split(":", 1)[1] if ":" in component else component

def load_delta_ranges(delta_path: str) -> dict[str, list[tuple[int,int]]]:
    with open(delta_path, "r", encoding="utf-8") as f:
        delta = json.load(f)

    ranges = {}
    for fobj in delta.get("files", []):
        path = fobj.get("path")
        lst = []
        for h in fobj.get("hunks", []):
            ns = int(h.get("new_start", 0))
            ne = int(h.get("new_end", -1))
            if ne >= ns and ns > 0:
                lst.append((ns, ne))
        ranges[path] = lst
    return ranges

def intersects(ranges: list[tuple[int,int]], start: int, end: int) -> bool:
    for a, b in ranges:
        if not (end < a or start > b):
            return True
    return False

def fetch_all_issues(token: str, project_key: str, pr: str, page_size: int = 500):
    issues = []
    page = 1
    while True:
        data = sonar_get(
            "/api/issues/search",
            token,
            {"componentKeys": project_key, "pullRequest": pr, "p": page, "ps": page_size},
        )
        issues.extend(data.get("issues", []))
        paging = data.get("paging", {})
        total = paging.get("total", len(issues))
        if len(issues) >= total:
            break
        page += 1
    return issues

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-key", required=True)
    ap.add_argument("--pr", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--delta", required=False, help="Path to delta.json to filter issues")
    args = ap.parse_args()

    token = os.environ.get("SONAR_TOKEN")
    if not token:
        raise SystemExit("Missing SONAR_TOKEN env var")

    qg, wait_meta = wait_for_pr_analysis(token, args.project_key, args.pr, timeout_s=90, sleep_s=3)
    qg_status = (qg or {}).get("projectStatus", {})
    status = (qg_status.get("status") or "NONE")

    issues = fetch_all_issues(token, args.project_key, args.pr)

    # Optional retry if QG ready but issues not yet visible
    if status != "NONE" and len(issues) == 0:
        time.sleep(3)
        issues = fetch_all_issues(token, args.project_key, args.pr)

    filtered = []
    filter_stats = {"file_not_touched": 0, "no_line_info": 0, "out_of_hunks": 0}

    if args.delta:
        delta_ranges = load_delta_ranges(args.delta)
        touched = set(delta_ranges.keys())

        for iss in issues:
            path = extract_path(iss.get("component", ""))
            if path not in touched:
                filter_stats["file_not_touched"] += 1
                continue

            tr = iss.get("textRange")
            line = iss.get("line")

            if tr:
                start = int(tr.get("startLine", 0))
                end = int(tr.get("endLine", start))
            elif line:
                start = end = int(line)
            else:
                filter_stats["no_line_info"] += 1
                continue

            if intersects(delta_ranges.get(path, []), start, end):
                iss2 = dict(iss)
                iss2["_delta_match"] = {"path": path, "start": start, "end": end}
                filtered.append(iss2)
            else:
                filter_stats["out_of_hunks"] += 1

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "qualityrisk.sonar_fetch",
            "version": "1.2.1",
        },
        "projectKey": args.project_key,
        "pullRequest": args.pr,
        "wait_for_analysis": wait_meta,
        "qualityGate": qg_status,
        "issues": issues,
        "issues_count": len(issues),
        "issues_filtered_by_delta": filtered,
        "issues_filtered_count": len(filtered),
        "filter_stats": filter_stats if args.delta else None,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()