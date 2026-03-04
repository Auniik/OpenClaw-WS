#!/usr/bin/env python3
"""Market-close runner (deterministic paths + bundler).

This runner solves the long-term determinism issues caused by mixing tool paths
with shell-only expansions like $(date ...).

It does NOT call the LLM itself.
Instead it:
- resolves a concrete data_dir inside the workspace state tree
- runs bundler.py to produce bundle-seed.txt
- writes paths.json so the cron agent can reliably read/write subsequent files

Downstream steps (planner/enrich/analyst) should use the concrete paths from
paths.json.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Paths:
    date: str
    data_dir: Path
    seed_path: Path
    plan_path: Path
    bundle_path: Path
    output_path: Path
    paths_json: Path


def now_dhaka_date() -> str:
    # Uses system timezone (OpenClaw host configured Asia/Dhaka)
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--outdir",
        default="/Users/anik/.openclaw/workspace/state/dse-trading",
        help="Workspace-local state root (tool-safe)",
    )
    ap.add_argument("--date", default="", help="Override date YYYY-MM-DD")
    ap.add_argument("--topn", type=int, default=30)
    args = ap.parse_args()

    date = (args.date or "").strip() or now_dhaka_date()
    state_root = Path(args.outdir)

    data_dir = state_root / date / "market-close"
    data_dir.mkdir(parents=True, exist_ok=True)

    seed_path = data_dir / "bundle-seed.txt"
    plan_path = data_dir / "plan.json"
    bundle_path = data_dir / "bundle.txt"
    output_path = data_dir / "ai-output.md"
    paths_json = data_dir / "paths.json"

    # Run bundler
    bundler = Path("/Users/anik/.openclaw/workspace/skills/dse-trading/scripts/market-close/bundler.py")
    run(["python3", str(bundler), "--out", str(seed_path), "--topn", str(args.topn)])

    p = Paths(
        date=date,
        data_dir=data_dir,
        seed_path=seed_path,
        plan_path=plan_path,
        bundle_path=bundle_path,
        output_path=output_path,
        paths_json=paths_json,
    )

    payload = {
        "date": p.date,
        "data_dir": str(p.data_dir),
        "seed_path": str(p.seed_path),
        "plan_path": str(p.plan_path),
        "bundle_path": str(p.bundle_path),
        "output_path": str(p.output_path),
        "paths_json": str(p.paths_json),
    }

    paths_json.write_text(dumps(payload) + "\n", encoding="utf-8")

    # Also print for logs
    print(dumps(payload))


if __name__ == "__main__":
    main()
