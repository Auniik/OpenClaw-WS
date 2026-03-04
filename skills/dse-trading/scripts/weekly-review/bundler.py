#!/usr/bin/env python3
"""Build a bundle for weekly DSE review.

Writes a single bundle.txt with compact sections suitable for LLM analysis.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _run(cmd: list[str], timeout_s: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout_s,
        )
        return p.returncode, (p.stdout or "")
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        return 124, (out + "\n[TIMEOUT]\n")


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def section(name: str, content: str) -> str:
    return f"== {name} ==\n{content.strip()}\n"


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=10)
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=max(3, int(args.days)))).strftime("%Y-%m-%d")

    meta = {
        "phase": "weekly-review",
        "timestamp": now.strftime("%Y-%m-%d %H:%M %Z"),
        "range": {"start": start_date, "end": end_date},
    }

    parts: list[str] = [section("meta", dumps(meta))]

    def add_cmd(label: str, cmd: list[str], timeout_s: int = 60) -> None:
        rc, out = _run(cmd, timeout_s=timeout_s)
        parts.append(section(label, out if out.strip() else f"(empty; rc={rc})"))

    # Market context
    add_cmd("market-summary", ["dse-ai", "market-summary", "--toon"], timeout_s=60)
    add_cmd("market-overview", ["dse-ai", "market-overview", "--toon"], timeout_s=60)
    add_cmd("dsex", ["dse-ai", "dsex", "--toon"], timeout_s=40)
    add_cmd("weekly-historical", ["dse-ai", "historical", "--start", start_date, "--end", end_date, "--toon"], timeout_s=120)

    # Breadth/rotation
    add_cmd("sectors", ["dse-ai", "sectors", "--toon"], timeout_s=60)
    add_cmd("top30", ["dse-ai", "top30", "--toon"], timeout_s=60)
    add_cmd("block-trades", ["dse-ai", "block-trades", "--toon"], timeout_s=60)
    add_cmd("global-markets", ["dse-ai", "global-markets", "--toon"], timeout_s=60)

    # Risk/compliance
    add_cmd("risk-screen", ["dse-ai", "risk-screen", "--toon"], timeout_s=60)
    add_cmd("compliance-non-submitted", ["dse-ai", "compliance", "--non-submitted", "--json"], timeout_s=60)
    add_cmd("compliance-delayed", ["dse-ai", "compliance", "--delayed", "--json"], timeout_s=60)
    add_cmd("circuit-upper", ["dse-ai", "circuit", "--upper", "--json"], timeout_s=60)
    add_cmd("circuit-lower", ["dse-ai", "circuit", "--lower", "--json"], timeout_s=60)

    # Portfolio (best effort)
    rc, out = _run(["dse-ai", "broker", "shanta", "portfolio", "--json"], timeout_s=120)
    parts.append(section("portfolio", out if out.strip() else f"(empty; rc={rc})"))

    rc, out = _run(["dse-ai", "broker", "shanta", "portfolio-trend", "90"], timeout_s=120)
    parts.append(section("portfolio-trend-90d", out if out.strip() else f"(empty; rc={rc})"))

    out_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
