#!/usr/bin/env python3
"""Mid-market runner (deterministic paths + bundler).

Does NOT call the LLM.
It only:
- resolves a concrete data_dir inside the workspace state tree
- runs bundler.py to produce bundle-seed.txt
- writes paths.json for downstream (planner/enrich/analyst)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Paths:
    run_date: str
    data_dir: Path
    seed_path: Path
    plan_path: Path
    bundle_path: Path
    output_path: Path
    paths_json: Path


def now_dhaka_date() -> str:
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
    ap.add_argument("--date", default="", help="Override run-date YYYY-MM-DD")
    ap.add_argument("--topn", type=int, default=30)
    args = ap.parse_args()

    run_date = (args.date or "").strip() or now_dhaka_date()
    state_root = Path(args.outdir)

    data_dir = state_root / run_date / "mid-market"
    data_dir.mkdir(parents=True, exist_ok=True)

    seed_path = data_dir / "bundle-seed.txt"
    plan_path = data_dir / "plan.json"
    bundle_path = data_dir / "bundle.txt"
    output_path = data_dir / "ai-output.md"
    paths_json = data_dir / "paths.json"

    bundler = Path("/Users/anik/.openclaw/workspace/skills/dse-trading/scripts/mid-market/bundler.py")
    run(["python3", str(bundler), "--out", str(seed_path), "--topn", str(args.topn)])

    payload = {
        "run_date": run_date,
        "data_dir": str(data_dir),
        "seed_path": str(seed_path),
        "plan_path": str(plan_path),
        "bundle_path": str(bundle_path),
        "output_path": str(output_path),
        "paths_json": str(paths_json),
    }

    paths_json.write_text(dumps(payload) + "\n", encoding="utf-8")
    print(dumps(payload))


if __name__ == "__main__":
    main()
