import argparse
import json
from datetime import datetime, timezone

def load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--delta", required=True)
    ap.add_argument("--sonar", required=True)
    ap.add_argument("--tests", required=True)
    ap.add_argument("--risk", required=False)
    ap.add_argument("--out", required=True)
    ap.add_argument("--policy-result", required=False)
    args = ap.parse_args()

    payload = {
        "meta": {
            "repo": args.repo,
            "pull_request": int(args.pr),
            "base_sha": args.base,
            "head_sha": args.head,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "format_version": "0.2.0",
        },
        "delta": load(args.delta),
        "tests": load(args.tests),
        "sonar": load(args.sonar),
    }

    if args.risk:
        payload["risk"] = load(args.risk)

    if args.policy_result:
        payload["policy"] = load(args.policy_result)    

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
