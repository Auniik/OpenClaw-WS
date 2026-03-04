#!/usr/bin/env python3
"""Enrich a seed bundle using a planner JSON.
This script appends minimal, decision-useful enrichment to the seed bundle:
- compact company snapshot fields (sector + marketInfo key levels)
- watchlist_enriched_table (CSV) with computed 20D highs/lows from historical JSON
- historical_last20 (TOON-like) per symbol (last 20 rows)

Writes only the final enriched bundle file.
"""

from __future__ import annotations

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
    # "31.70 - 33.60"
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

    # dse-ai returns most-recent-first; keep that order for scanning.
    rows20 = [r for r in rows if isinstance(r, dict)][:20]

    cols = ["DATE", "OPENP*", "HIGH", "LOW", "CLOSEP*", "VALUE (mn)", "VOLUME"]
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

    # Date range
    end_date = str(plan.get("date") or meta.get("date") or "").strip()
    if not end_date:
        end_date = datetime.now().astimezone().strftime("%Y-%m-%d")

    history_days = int(plan.get("historyDays") or 20)
    calendar_days = max(10, int(history_days * args.calendarFactor))

    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception:
        end_dt = datetime.now().astimezone().replace(tzinfo=None)
    start_dt = end_dt - timedelta(days=calendar_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    company_min: dict[str, dict] = {}
    historical: dict[str, dict] = {}

    for sym in symbols:
        cobj = sh_json(["dse-ai", "company", sym, "--json"])
        market = cobj.get("marketInfo") if isinstance(cobj, dict) else None
        basic_sector = cobj.get("sector") if isinstance(cobj, dict) else None

        if not isinstance(market, dict):
            market = {}

        day_low, day_high = parse_day_range(str(market.get("dayRange") or ""))
        wk52_low, wk52_high = parse_day_range(str(market.get("fiftyTwoWeekRange") or ""))

        company_min[sym] = {
            "sector": basic_sector,
            "lastUpdate": market.get("lastUpdate"),
            "ltp": market.get("ltp") or market.get("closingPrice"),
            "yesterdayClose": market.get("yesterdayClose"),
            "day_low": day_low,
            "day_high": day_high,
            "wk52_low": wk52_low,
            "wk52_high": wk52_high,
            "dayValue_mn": market.get("dayValue"),
            "dayVolume": market.get("dayVolume"),
        }

        historical[sym] = sh_json(
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

    # Build watchlist_enriched_table (CSV)
    # Also compute a suggested trade mode + R-based targets (derived only from bundle fields).
    enriched_rows: list[dict] = []

    def _entry(day_high: float | None, d_high: float | None) -> float | None:
        cands = [x for x in (day_high, d_high) if isinstance(x, (int, float))]
        return max(cands) if cands else None

    def _mode(entry_v: float | None, day_high: float | None, d_high: float | None) -> str:
        # SHORT if today's high is effectively the breakout trigger (near rolling high), else SWING.
        if entry_v is None or day_high is None or d_high is None:
            return "SWING"
        if abs(day_high - d_high) <= max(0.01, 0.003 * entry_v):
            return "SHORT"
        return "SWING"

    def _risk_targets(entry_v: float | None, stop_v: float | None) -> tuple[float | None, float | None, float | None]:
        if entry_v is None or stop_v is None:
            return (None, None, None)
        r = entry_v - stop_v
        if r <= 0:
            return (None, None, None)
        return (r, entry_v + r, entry_v + 2 * r)

    for sym in symbols:
        cm = company_min.get(sym) or {}
        hm = historical_metrics(historical.get(sym) or {})

        day_low = cm.get("day_low") if isinstance(cm.get("day_low"), (int, float)) else fnum(cm.get("day_low"))
        day_high = cm.get("day_high") if isinstance(cm.get("day_high"), (int, float)) else fnum(cm.get("day_high"))
        d_low = hm.get("low") if isinstance(hm.get("low"), (int, float)) else fnum(hm.get("low"))
        d_high = hm.get("high") if isinstance(hm.get("high"), (int, float)) else fnum(hm.get("high"))

        entry_v = _entry(day_high, d_high)
        mode = _mode(entry_v, day_high, d_high)

        # stops: SHORT uses day_low; SWING uses min(day_low, rolling_low)
        short_sl = day_low
        swing_sl = None
        if day_low is not None and d_low is not None:
            swing_sl = min(day_low, d_low)
        else:
            swing_sl = day_low or d_low

        stop_v = short_sl if mode == "SHORT" else swing_sl
        r, t1, t2 = _risk_targets(entry_v, stop_v)

        enriched_rows.append(
            {
                "code": sym,
                "sector": cm.get("sector") or "",
                "mode": mode,
                "ltp": cm.get("ltp") or "",
                "ycp": cm.get("yesterdayClose") or "",
                "day_low": day_low or "",
                "day_high": day_high or "",
                "low": d_low or "",
                "high": d_high or "",
                "52w_low": cm.get("wk52_low") or "",
                "52w_high": cm.get("wk52_high") or "",
                "entry": entry_v or "",
                "stop": stop_v or "",
                "R": r or "",
                "T1_1R": t1 or "",
                "T2_2R": t2 or "",
                "value_mn": cm.get("dayValue_mn") or "",
                "volume": cm.get("dayVolume") or "",
            }
        )

    # historical_last20 (TOON-like) per symbol
    hist_toon_parts: list[str] = []
    for sym in symbols:
        hist_toon_parts.append(f"-- {sym} --\n" + historical_last20_toon(historical.get(sym) or {}))

    # Write enriched bundle
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = seed_text.rstrip() + "\n\n"
    text += "== plan ==\n" + dumps(plan) + "\n\n"  # compact json
    text += "== company_min ==\n" + dumps(company_min) + "\n\n"  # compact json (minimal fields)
    text += (
        "== watchlist_enriched_table ==\n"
        + to_csv(
            enriched_rows,
            [
                "code",
                "sector",
                "mode",
                "ltp",
                "ycp",
                "day_low",
                "day_high",
                "low",
                "high",
                "52w_low",
                "52w_high",
                "entry",
                "stop",
                "R",
                "T1_1R",
                "T2_2R",
                "value_mn",
                "volume",
            ],
        )
        + "\n\n"
    )
    text += "== historical_last20 ==\n" + "\n\n".join(hist_toon_parts) + "\n"

    out_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
