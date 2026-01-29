import argparse
import json
import subprocess
import time
from datetime import datetime, timezone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--", dest="cmd_sep", action="store_true")  # ignored
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    if not args.cmd:
        raise SystemExit("No command provided. Usage: run_cmd_capture.py --name X --out Y -- <command>")

    started = time.time()
    started_iso = datetime.now(timezone.utc).isoformat()

    proc = subprocess.run(args.cmd, text=True, capture_output=True)
    ended = time.time()

    payload = {
        "name": args.name,
        "started_at": started_iso,
        "duration_sec": round(ended - started, 3),
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-20000:],  # evita artefactos gigantes
        "stderr": proc.stderr[-20000:],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # Si quieres que el workflow falle cuando fallen tests, descomenta:
    # if proc.returncode != 0:
    #     raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
