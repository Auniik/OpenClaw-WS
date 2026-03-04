#!/usr/bin/env python3
"""Enrich a market-open seed bundle using a planner JSON.

Symmetric with pre-market/enrich.py and market-close/enrich.py.

Adds:
- company_min: compact company snapshot fields (sector + key marketInfo levels)
- watchlist_enriched_table (CSV) with computed 20D highs/lows + simple R targets
- historical_last20 (TOON-like) per symbol (last 20 rows)

Writes only the final enriched bundle file.
"""

from __future__ import annotations

# Keep this file intentionally aligned with scripts/pre-market/enrich.py.

import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return p.stdout or ""


def _json_from_maybe_preambled(output: str) -> dict:
    s = (output or "").strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    i = s.find("{")
    if i >= 0:
        try:
            obj = json.loads(s[i:])
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def sh_json(args: list[str]) -> dict:
    return _json_from_maybe_preambled(_run(args))


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def to_csv(rows: list[dict], cols: list[str]) -> str:
    lines = [",".join(cols)]
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c, "")
            v = "" if v is None else str(v)
            v = v.replace("\n", " ").replace(",", " ").strip()
            vals.append(v)
        lines.append(",".join(vals))
    return "\n".join(lines)


def parse_seed_meta(seed_text: str) -> dict:
    marker = "== meta =="
    if marker not in seed_text:
        return {}
    after = seed_text.split(marker, 1)[1].lstrip("\n")
    line = after.splitlines()[0].strip() if after else ""
    try:
        obj = json.loads(line)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def parse_day_range(s: str) -> tuple[float | None, float | None]:
    if not isinstance(s, str):
        return (None, None)
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)", s)
    if not m:
        return (None, None)
    try:
        lo = float(m.group(1))
        hi = float(m.group(2))
        return (lo, hi)
    except Exception:
        return (None, None)


def fnum(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        t = x.replace(",", "").strip()
        if t in ("", "-"):
            return None
        try:
            return float(t)
        except Exception:
            return None
    return None


def historical_metrics(hist: dict) -> dict:
    rows = hist.get("data")
    if not isinstance(rows, list):
        return {"high": None, "low": None}

    highs: list[float] = []
    lows: list[float] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        hi = fnum(r.get("HIGH") or r.get("high"))
        lo = fnum(r.get("LOW") or r.get("low"))
        if hi is not None:
            highs.append(hi)
        if lo is not None:
            lows.append(lo)

    return {
        "high": max(highs) if highs else None,
        "low": min(lows) if lows else None,
    }


def historical_last20_toon(hist: dict) -> str:
    rows = hist.get("data")
    if not isinstance(rows, list):
        return "(no historical data)"

    rows20 = [r for r in rows if isinstance(r, dict)][:20]

    out = [
        f"data[{len(rows20)}]{{date,open,high,low,close,value_mn,volume}}:",
    ]

    for r in rows20:
        date = str(r.get("DATE") or "")
        op = str(r.get("OPENP*") or "")
        hi = str(r.get("HIGH") or "")
        lo = str(r.get("LOW") or "")
        cl = str(r.get("CLOSEP*") or "")
        val = str(r.get("VALUE (mn)") or "")
        vol = str(r.get("VOLUME") or "")
        out.append(f"  {date}," + ",".join([op, hi, lo, cl, val, vol]))

    return "\n".join(out)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--calendarFactor", type=float, default=1.6, help="calendar days = historyDays * factor")
    args = ap.parse_args()

    seed_path = Path(args.seed)
    plan_path = Path(args.plan)
    out_path = Path(args.out)

    seed_text = seed_path.read_text(encoding="utf-8", errors="replace")
    meta = parse_seed_meta(seed_text)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    symbols = plan.get("fetch", {}).get("symbols") or []
    if not isinstance(symbols, list):
        symbols = []
    symbols = [s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()]
    symbols = [s for s in symbols if CODE_RE.fullmatch(s)]
    symbols = sorted(set(symbols))

    # Date range: prefer plan.date, fall back to meta.asof_date (market date), else now.
    end_date = str(plan.get("date") or meta.get("asof_date") or meta.get("date") or "").strip()
    if not end_date:
        end_date = datetime.now().astimezone().strftime("%Y-%m-%d")

    history_days = int(plan.get("historyDays") or 60)
    calendar_days = max(10, int(history_days * args.calendarFactor))

    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception:
        end_dt = datetime.now().astimezone().replace(tzinfo=None)
    start_dt = end_dt - timedelta(days=calendar_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    company_min: dict[str, dict] = {}
    enriched_rows: list[dict] = []
    hist_toon_parts: list[str] = []

    def _entry(mode: str, ltp: float | None, ycp: float | None) -> float | None:
        # At market-open we can anchor to current ltp if available; else ycp.
        if ltp is not None:
            return ltp
        return ycp

    def _mode(wk52_lo: float | None, wk52_hi: float | None, ycp: float | None) -> str:
        if wk52_lo is None or wk52_hi is None or ycp is None:
            return "SHORT"
        if wk52_hi > 0 and (wk52_hi - ycp) / wk52_hi < 0.12:
            return "SWING"
        return "SHORT"

    def _risk_targets(entry_v: float | None, stop_v: float | None) -> tuple[float | None, float | None, float | None]:
        if entry_v is None or stop_v is None:
            return (None, None, None)
        r = abs(entry_v - stop_v)
        if r <= 0:
            return (None, None, None)
        t1 = entry_v + r
        t2 = entry_v + 2 * r
        return (r, t1, t2)

    for sym in symbols:
        cobj = sh_json(["dse-ai", "company", sym, "--json"])
        market = cobj.get("marketInfo") if isinstance(cobj, dict) else {}
        if not isinstance(market, dict):
            market = {}

        sector = str(cobj.get("sector") or "")
        day_range = str(market.get("dayRange") or "")
        wk52_range = str(market.get("fiftyTwoWeekRange") or "")

        day_lo, day_hi = parse_day_range(day_range)
        wk52_lo, wk52_hi = parse_day_range(wk52_range)

        ycp = fnum(market.get("yesterdayClose") or market.get("YCP") or market.get("ycp"))
        ltp = fnum(market.get("ltp") or market.get("LTP") or market.get("ltp"))

        company_min[sym] = {
            "sector": sector,
            "marketInfo": {
                "lastUpdate": market.get("lastUpdate") or "",
                "ltp": market.get("ltp") or market.get("LTP") or "",
                "closingPrice": market.get("closingPrice") or "",
                "yesterdayClose": market.get("yesterdayClose") or market.get("YCP") or market.get("ycp") or "",
                "dayRange": day_range,
                "fiftyTwoWeekRange": wk52_range,
            },
        }

        mode = _mode(wk52_lo, wk52_hi, ycp)
        entry = _entry(mode, ltp, ycp)

        stop = None
        if entry is not None:
            # Use day_low if available, else a conservative % stop.
            if day_lo is not None:
                stop = day_lo
            else:
                stop = entry * (0.97 if mode == "SHORT" else 0.94)

        r, t1, t2 = _risk_targets(entry, stop)

        hist = sh_json(
            [
                "dse-ai",
                "historical",
                "--start",
                start_date,
                "--end",
                end_date,
                "--inst",
                sym,
                "--json",
            ]
        )

        hm = historical_metrics(hist)
        hist_toon = historical_last20_toon(hist)

        enriched_rows.append(
            {
                "code": sym,
                "sector": sector,
                "mode": mode,
                "ycp": ycp if ycp is not None else "",
                "ltp": ltp if ltp is not None else "",
                "day_low": day_lo if day_lo is not None else "",
                "day_high": day_hi if day_hi is not None else "",
                "wk52_low": wk52_lo if wk52_lo is not None else "",
                "wk52_high": wk52_hi if wk52_hi is not None else "",
                "high_rolling": hm.get("high") if hm.get("high") is not None else "",
                "low_rolling": hm.get("low") if hm.get("low") is not None else "",
                "entry": entry if entry is not None else "",
                "stop": stop if stop is not None else "",
                "R": r if r is not None else "",
                "T1_1R": t1 if t1 is not None else "",
                "T2_2R": t2 if t2 is not None else "",
            }
        )

        hist_toon_parts.append(f"-- {sym} --\n" + hist_toon)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []
    parts.append(seed_text.strip())
    parts.append("== plan ==\n" + dumps(plan))
    parts.append("== company_min ==\n" + dumps(company_min))

    cols = [
        "code",
        "sector",
        "mode",
        "ycp",
        "ltp",
        "day_low",
        "day_high",
        "wk52_low",
        "wk52_high",
        "high_rolling",
        "low_rolling",
        "entry",
        "stop",
        "R",
        "T1_1R",
        "T2_2R",
    ]
    parts.append("== watchlist_enriched_table ==\n" + to_csv(enriched_rows, cols))
    parts.append("== historical_last20 ==\n" + "\n\n".join(hist_toon_parts))

    out_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
