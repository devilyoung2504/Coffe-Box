#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

MAX_CAPTURE_CHARS = 20000

NO_TESTS_PATTERNS = [
    re.compile(r"\bNo tests found\b", re.IGNORECASE),
    re.compile(r"\b0 tests\b", re.IGNORECASE),
    re.compile(r"\bCollected 0 items\b", re.IGNORECASE),
]

OUTPUT_TEST_SIGNALS = [
    re.compile(r"\bPASS\b"),
    re.compile(r"\bFAIL\b"),
    re.compile(r"\btests?\b", re.IGNORECASE),
    re.compile(r"\bpassed\b", re.IGNORECASE),
    re.compile(r"\bfailing\b", re.IGNORECASE),
]

TEST_FILE_PATTERNS = [
    re.compile(r".*/__tests__/.*"),
    re.compile(r".*\.test\.(js|jsx|ts|tsx)$"),
    re.compile(r".*\.spec\.(js|jsx|ts|tsx)$"),
    re.compile(r".*test_.*\.py$"),
]

def trunc(s: str):
    if s is None:
        return "", False
    if len(s) <= MAX_CAPTURE_CHARS:
        return s, False
    return s[-MAX_CAPTURE_CHARS:] + "\n...[truncated]...", True

def find_test_files(root: str) -> list[str]:
    hits = []
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        s = str(p).replace("\\", "/")
        for pat in TEST_FILE_PATTERNS:
            if pat.match(s):
                hits.append(s)
                break
        if len(hits) >= 200:
            break
    return hits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    # Soporta: python script.py --name X --out Y -- npm test
    if args.cmd and args.cmd[0] == "--":
        args.cmd = args.cmd[1:]

    if not args.cmd:
        raise SystemExit("No command provided. Usage: run_cmd_capture.py --name X --out Y -- <command>")

    started = time.time()
    started_iso = datetime.now(timezone.utc).isoformat()

    proc = subprocess.run(args.cmd, text=True, capture_output=True)
    ended = time.time()

    stdout, stdout_tr = trunc(proc.stdout or "")
    stderr, stderr_tr = trunc(proc.stderr or "")
    duration_ms = int((ended - started) * 1000)

    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    output_says_no_tests = any(rx.search(combined) for rx in NO_TESTS_PATTERNS)
    output_mentions_tests = any(rx.search(combined) for rx in OUTPUT_TEST_SIGNALS)

    test_files = find_test_files(".")
    has_test_files = len(test_files) > 0

    if output_says_no_tests:
        tests_present = False
    else:
        tests_present = bool(output_mentions_tests or has_test_files)

    tests_passed = bool(tests_present and proc.returncode == 0)

    payload = {
        "name": args.name,
        "started_at": started_iso,
        "duration_ms": duration_ms,
        "exit_code": proc.returncode,
        "tests_present": tests_present,
        "tests_passed": tests_passed,
        "signals": {
            "has_test_files": has_test_files,
            "test_files_sample": test_files[:25],
            "output_mentions_tests": output_mentions_tests,
            "output_says_no_tests": output_says_no_tests,
        },
        "stdout": stdout,
        "stderr": stderr,
        "truncated": {"stdout": stdout_tr, "stderr": stderr_tr},
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
