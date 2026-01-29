import argparse
import json
import re
import subprocess


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

def sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # Status por archivo (M/A/D/R)
    name_status = sh(["git", "diff", "--name-status", f"{args.base}..{args.head}"]).splitlines()
    status_map = {}
    for line in name_status:
        if not line.strip():
            continue
        parts = line.split("\t")
        st = parts[0]
        path = parts[-1]
        status_map[path] = st

    # Numstat (adds/dels)
    numstat = sh(["git", "diff", "--numstat", f"{args.base}..{args.head}"]).splitlines()
    stats_map = {}
    for line in numstat:
        if not line.strip():
            continue
        a, d, path = line.split("\t")
        stats_map[path] = {"additions": a, "deletions": d}

    # Hunks (líneas tocadas)
    diff = sh(["git", "diff", "--unified=0", f"{args.base}..{args.head}"])
    files = {}
    current = None

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[len("+++ b/"):].strip()
            files.setdefault(current, {"hunks": []})
        elif line.startswith("@@") and current:
            m = HUNK_RE.match(line)
            if m:
                old_start = int(m.group(1))
                old_len = int(m.group(2) or "1")
                new_start = int(m.group(3))
                new_len = int(m.group(4) or "1")
                files[current]["hunks"].append({
                    "old_start": old_start,
                    "old_len": old_len,
                    "new_start": new_start,
                    "new_len": new_len,
                })

    out_files = []
    total_add = 0
    total_del = 0

    for path, data in files.items():
        st = status_map.get(path, "M")
        nd = stats_map.get(path, {"additions": "0", "deletions": "0"})
        # numstat puede traer "-" para binarios
        add = int(nd["additions"]) if nd["additions"].isdigit() else 0
        dele = int(nd["deletions"]) if nd["deletions"].isdigit() else 0
        total_add += add
        total_del += dele

        out_files.append({
            "path": path,
            "status": st,
            "additions": add,
            "deletions": dele,
            "hunks": data["hunks"],
        })

    payload = {
        "base": args.base,
        "head": args.head,
        "stats": {
            "files_changed": len(out_files),
            "additions": total_add,
            "deletions": total_del,
        },
        "files": out_files,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
