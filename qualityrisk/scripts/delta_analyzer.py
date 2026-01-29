#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone

HUNK_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

def sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)

def head_file_set() -> set[str]:
    out = sh(["git", "ls-tree", "-r", "--name-only", "HEAD"])
    return set(l.strip() for l in out.splitlines() if l.strip())

def parse_name_status(line: str):
    # M\tpath
    # A\tpath
    # D\tpath
    # R100\told\tnew
    parts = line.split("\t")
    st = parts[0]
    if st.startswith(("R", "C")) and len(parts) >= 3:
        return st, parts[1], parts[2]  # old, new
    return st, None, parts[1]

def should_ignore(path: str, ignore_paths: set[str], ignore_prefixes: list[str]) -> bool:
    if path in ignore_paths:
        return True
    return any(path.startswith(p) for p in ignore_prefixes)

def file_numstat(base: str, head: str, path: str) -> tuple[int, int]:
    out = sh(["git", "diff", "--numstat", f"{base}..{head}", "--", path]).strip()
    if not out:
        return 0, 0
    a, d, _ = out.split("\t", 2)
    add = int(a) if a.isdigit() else 0
    dele = int(d) if d.isdigit() else 0
    return add, dele

def file_hunks(base: str, head: str, path: str):
    diff = sh(["git", "diff", "--no-color", "--unified=0", f"{base}..{head}", "--", path])
    hunks = []
    for line in diff.splitlines():
        if not line.startswith("@@ "):
            continue
        m = HUNK_RE.match(line)
        if not m:
            continue
        old_start = int(m.group(1))
        old_len = int(m.group(2) or "1")
        new_start = int(m.group(3))
        new_len = int(m.group(4) or "1")

        old_end = old_start + old_len - 1 if old_len > 0 else old_start - 1
        new_end = new_start + new_len - 1 if new_len > 0 else new_start - 1

        hunks.append({
            "header": line,
            "old_start": old_start, "old_len": old_len, "old_end": old_end,
            "new_start": new_start, "new_len": new_len, "new_end": new_end,
            "deletion_only": (new_len == 0),
        })
    return hunks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ignore-path", action="append", default=[".gitignore"])
    ap.add_argument("--ignore-prefix", action="append", default=["node_modules/", "qualityrisk/out/"])
    args = ap.parse_args()

    head_files = head_file_set()

    name_status = sh(["git", "diff", "--name-status", f"{args.base}..{args.head}"]).splitlines()

    out_files = []
    totals_add = 0
    totals_del = 0

    deleted_files = []

    for raw in name_status:
        if not raw.strip():
            continue

        st, old_path, path = parse_name_status(raw)
        st_norm = st[0]  # M/A/D/R/C...

        # Ignora paths irrelevantes
        if should_ignore(path, set(args.ignore_path), args.ignore_prefix):
            continue

        # Deleted: no existe en HEAD -> no rangos nuevos
        if st_norm == "D" or path not in head_files:
            deleted_files.append({"path": path, "status": st})
            continue

        add, dele = file_numstat(args.base, args.head, path)
        hunks = file_hunks(args.base, args.head, path)

        totals_add += add
        totals_del += dele

        out_files.append({
            "path": path,
            "status": st,
            **({"previous_path": old_path} if old_path else {}),
            "additions": add,
            "deletions": dele,
            "hunks": hunks,
        })

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "qualityrisk.delta_analyzer",
            "version": "1.2.0",
            "base": args.base,
            "head": args.head,
        },
        "stats": {
            "files_changed": len(out_files),
            "additions": totals_add,
            "deletions": totals_del,
            "churn_lines": totals_add + totals_del,
            "deleted_files": len(deleted_files),
        },
        "files": out_files,
        "deleted": deleted_files,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
