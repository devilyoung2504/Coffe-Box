import argparse
import json
import os
import requests


SONAR_HOST = "https://sonarcloud.io"

def sonar_get(path: str, token: str, params: dict):
    url = f"{SONAR_HOST}{path}"
    r = requests.get(url, params=params, auth=(token, ""))
    r.raise_for_status()
    return r.json()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-key", required=True)
    ap.add_argument("--pr", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    token = os.environ.get("SONAR_TOKEN")
    if not token:
        raise SystemExit("Missing SONAR_TOKEN env var")

    # Quality Gate del PR
    qg = sonar_get(
        "/api/qualitygates/project_status",
        token,
        {"projectKey": args.project_key, "pullRequest": args.pr},
    )

    # Issues del PR (paginación básica)
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

    payload = {
        "projectKey": args.project_key,
        "pullRequest": args.pr,
        "qualityGate": qg.get("projectStatus", {}),
        "issues": issues,
        "issues_count": len(issues),
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
