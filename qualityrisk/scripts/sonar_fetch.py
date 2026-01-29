#!/usr/bin/env python3
import argparse
import json
import os
import requests
from datetime import datetime, timezone

SONAR_HOST = "https://sonarcloud.io"

def sonar_get(path: str, token: str, params: dict):
    url = f"{SONAR_HOST}{path}"
    r = requests.get(url, params=params, auth=(token, ""))
    r.raise_for_status()
    return r.json()

def extract_path(component: str) -> str:
    # Ej: "projectKey:qualityrisk/scripts/delta_analyzer.py"
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

    qg = sonar_get(
        "/api/qualitygates/project_status",
        token,
        {"projectKey": args.project_key, "pullRequest": args.pr},
    )

    issues = []
    page = 1
    page_size = 500
    while True:
        data = sonar_get(
            "/api/issues/search",
            token,
            {
                "componentKeys": args.project_key,
                "pullRequest": args.pr,
                "p": page,
                "ps": page_size,
            },
        )
        issues.extend(data.get("issues", []))
        paging = data.get("paging", {})
        total = paging.get("total", len(issues))
        if len(issues) >= total:
            break
        page += 1

    filtered = []
    filter_stats = {"file_not_touched": 0, "no_line_info": 0, "out_of_hunks": 0}

    delta_ranges = None
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
                # issue a nivel archivo (sin línea): lo dejamos fuera por default (más estricto)
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
            "version": "1.2.0",
        },
        "projectKey": args.project_key,
        "pullRequest": args.pr,
        "qualityGate": qg.get("projectStatus", {}),
        "issues": issues,
        "issues_count": len(issues),
        "issues_filtered_by_delta": filtered,
        "issues_filtered_count": len(filtered),
        "filter_stats": filter_stats if args.delta else None,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
