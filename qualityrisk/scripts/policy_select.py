#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

TOOLING_ALLOWLIST = {
    ".github/workflows/qualityrisk.yml",
}

def load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def is_tooling_path(p: str) -> bool:
    return p.startswith("qualityrisk/") or p in TOOLING_ALLOWLIST

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", required=True)
    ap.add_argument("--web-policy", required=True)
    ap.add_argument("--tooling-policy", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    delta = load_json(args.delta)
    files = [f.get("path","") for f in (delta.get("files") or [])]
    files = [p for p in files if p]

    if files and all(is_tooling_path(p) for p in files):
        selected = args.tooling_policy
    else:
        selected = args.web_policy

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(selected + "\n", encoding="utf-8")
    print(f"Selected policy: {selected}")

if __name__ == "__main__":
    main()
