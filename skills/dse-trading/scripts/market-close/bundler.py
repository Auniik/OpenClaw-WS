#!/usr/bin/env python3
"""
Build a minimal *seed* bundle for market-close.
This script writes only the seed bundle.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import datetime
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


def sh_json_retry(args: list[str], tries: int = 3) -> dict:
    """Retry JSON fetch. Useful for flaky endpoints like broker portfolio."""
    last: dict = {}
    for _ in range(max(1, tries)):
        last = sh_json(args)
        if last:
            return last
    return last


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def code_from_row(r: Any) -> str | None:
    if not isinstance(r, dict):
        return None
    for k in ("tradingCode", "TRADING CODE", "Trade Code", "code", "symbol", "instrCode"):
        v = r.get(k)
        if isinstance(v, str):
            c = v.strip()
            if CODE_RE.fullmatch(c):
                return c
    return None


def pick_list(obj: dict, keys: tuple[str, ...]) -> list[dict]:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, list) and any(isinstance(x, dict) for x in v):
            return [x for x in v if isinstance(x, dict)]
    for v in obj.values():
        if isinstance(v, list) and any(isinstance(x, dict) for x in v):
            return [x for x in v if isinstance(x, dict)]
    return []


def _codes_from_submissions(obj: dict) -> list[str]:
    subs = obj.get("submissions")
    if not isinstance(subs, list):
        return []
    out: list[str] = []
    for s in subs:
        if isinstance(s, dict) and isinstance(s.get("tradingCode"), str):
            c = re.sub(r"\s*\*+\s*$", "", s["tradingCode"].strip())
            if CODE_RE.fullmatch(c) and c not in out:
                out.append(c)
    return out


def top_codes(latest_obj: dict, n: int = 30) -> list[str]:
    rows = pick_list(latest_obj, ("data", "latest", "rows"))
    out: list[str] = []
    for r in rows:
        c = code_from_row(r)
        if c and c not in out:
            out.append(c)
        if len(out) >= n:
            break
    return out


def build_shortlist(holdings: set[str], top_change: list[str], top_value: list[str], top_volume: list[str]) -> dict[str, list[str]]:
    sources: dict[str, set[str]] = {}

    def add(code: str, src: str) -> None:
        sources.setdefault(code, set()).add(src)

    for c in holdings:
        add(c, "holding")
    for c in top_change:
        add(c, "top_change")
    for c in top_value:
        add(c, "top_value")
    for c in top_volume:
        add(c, "top_volume")

    return {c: sorted(list(srcs)) for c, srcs in sorted(sources.items())}


def build_focus_rows(dsex_obj: dict, focus_codes: set[str]) -> tuple[list[dict], list[str]]:
    rows = pick_list(dsex_obj, ("data", "rows"))
    idx: dict[str, dict] = {}
    for r in rows:
        c = code_from_row(r)
        if c:
            idx[c] = r

    def pick(r: dict, keys: list[str]) -> Any:
        for k in keys:
            if k in r and r.get(k) not in (None, ""):
                return r.get(k)
        return ""

    out: list[dict] = []
    missing: list[str] = []
    for c in sorted(focus_codes):
        r = idx.get(c)
        if not r:
            missing.append(c)
            continue
        out.append(
            {
                "code": c,
                "ltp": pick(r, ["LTP*", "LTP", "ltp"]),
                "ycp": pick(r, ["YCP*", "YCP", "ycp"]),
                "pct_change": pick(r, ["% CHANGE", "pctChange", "change", "percentChange", "percent_change"]),
                "value_mn": pick(r, ["VALUE (mn)", "value", "valueMn", "value_mn", "tradeValue", "trade_value"]),
                "volume": pick(r, ["VOLUME", "volume", "tradeVolume", "trade_volume"]),
            }
        )
    return out, missing


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


def build_momentum_rows(obj: dict, n: int = 10) -> list[dict]:
    rows = pick_list(obj, ("data", "latest", "rows"))

    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        c = code_from_row(r)
        if not c:
            continue

        # gainers/losers use slightly different keys
        pct = r.get("% CHANGE") or r.get("pct_change") or r.get("pctChange") or ""
        val = r.get("VALUE (mn)") or r.get("value_mn") or r.get("valueMn") or ""

        out.append({"code": c, "pct_change": pct, "value_mn": val})
        if len(out) >= n:
            break

    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output seed bundle file")
    ap.add_argument("--topn", type=int, default=30)
    args = ap.parse_args()

    ts = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    market_stats = sh_json(["dse-ai", "market-stats", "--json"])
    date = str(market_stats.get("date") or "") or datetime.now().astimezone().strftime("%Y-%m-%d")

    summary_recent = sh_json(["dse-ai", "summary", "--recent", "--json"])

    risk_screen_raw = sh_json(["dse-ai", "risk-screen", "--json"])
    threats = pick_list(risk_screen_raw, ("threats", "data", "rows"))
    risk_codes = []
    for t in threats:
        if isinstance(t, dict):
            c = t.get("tradingCode") or t.get("TRADING CODE") or t.get("Trade Code")
            if isinstance(c, str) and CODE_RE.fullmatch(c.strip()):
                risk_codes.append(c.strip())
    risk_codes = sorted(set(risk_codes))

    # circuit codes (list)
    # circuit codes will be extracted after we fetch circuit_raw (below)
    circuit_codes: list[str] = []

    compliance_non_raw = sh_json(["dse-ai", "compliance", "--non-submitted", "--json"])
    compliance_del_raw = sh_json(["dse-ai", "compliance", "--delayed", "--json"])

    # Circuit breaker (risk signal)
    circuit_raw = sh_json(["dse-ai", "circuit", "--json"])
    circuit_rows = pick_list(circuit_raw, ("data", "rows"))
    circuit_codes_tmp: list[str] = []
    for r in circuit_rows:
        if not isinstance(r, dict):
            continue
        c = r.get("Trade Code") or r.get("TRADING CODE") or r.get("tradingCode") or r.get("code")
        if isinstance(c, str) and CODE_RE.fullmatch(c.strip()):
            circuit_codes_tmp.append(c.strip())
    circuit_codes = sorted(set(circuit_codes_tmp))

    portfolio = sh_json_retry(["dse-ai", "broker", "shanta", "portfolio", "--json"], tries=3)

    holdings: set[str] = set()
    holdings_rows: list[dict] = []
    for r in (portfolio.get("stocks") or []):
        if not isinstance(r, dict):
            continue
        c = r.get("symbol") or r.get("symbole")
        if isinstance(c, str) and CODE_RE.fullmatch(c.strip()):
            code = c.strip()
            holdings.add(code)
            holdings_rows.append(
                {
                    "code": code,
                    "shares": r.get("quantity") or r.get("shares") or "",
                    "avg_cost": r.get("costPrice") or "",
                    "mkt_price": r.get("marketPrice") or r.get("price") or "",
                    "pnl_pct": str(r.get("percentage") or "").replace("%", ""),
                }
            )

    latest_change = sh_json(["dse-ai", "latest", "--by-change", "--json"])
    latest_value = sh_json(["dse-ai", "latest", "--by-value", "--json"])
    latest_volume = sh_json(["dse-ai", "latest", "--by-volume", "--json"])

    gainers_obj = sh_json(["dse-ai", "gainers", "--json"])
    losers_obj = sh_json(["dse-ai", "losers", "--json"])

    top_change = top_codes(latest_change, args.topn)
    top_value = top_codes(latest_value, args.topn)
    top_volume = top_codes(latest_volume, args.topn)

    shortlist = build_shortlist(holdings, top_change, top_value, top_volume)
    focus_codes = set(shortlist.keys())

    dsex_obj = sh_json(["dse-ai", "dsex", "--json"])
    focus_rows, missing_focus = build_focus_rows(dsex_obj, focus_codes)

    # compliance reduce-junk
    non_set = set(_codes_from_submissions(compliance_non_raw))
    del_set = set(_codes_from_submissions(compliance_del_raw))

    subs_non = compliance_non_raw.get("submissions") if isinstance(compliance_non_raw, dict) else None
    if not isinstance(subs_non, list):
        subs_non = []
    c_non = Counter(
        re.sub(r"\s*\*+\s*$", "", s["tradingCode"].strip())
        for s in subs_non
        if isinstance(s, dict) and isinstance(s.get("tradingCode"), str)
    )
    compliance_summary = {
        "total_non_submission_companies": len(subs_non),
        "top_non_submission_counts": {code: cnt for code, cnt in c_non.most_common(10)},
    }

    focus_set = set(focus_codes)
    movers_set = set(top_change) | set(top_value) | set(top_volume)
    compliance = {
        "summary": compliance_summary,
        "non_submission": sorted(list(focus_set & non_set)),
        "delayed_submission": {
            "holdings": sorted(list(holdings & del_set)),
            "movers": sorted(list(movers_set & del_set)),
        },
    }

    seed_meta = {"phase": "market-close", "timestamp": ts, "date": date, "topn": args.topn}

    # Write seed bundle in requested formats
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []

    # 1) compact json
    parts.append("== meta ==\n" + dumps(seed_meta))
    parts.append("== market_stats ==\n" + dumps(market_stats))
    parts.append("== summary_recent ==\n" + dumps(summary_recent))

    # 3) risk screen as json list
    parts.append("== risk_screen_codes ==\n" + dumps(risk_codes))

    # circuit as json list + compact hits summary
    parts.append("== circuit_codes ==\n" + dumps(circuit_codes))
    circuit_hits = {
        "holdings_hit": sorted(list(holdings & set(circuit_codes))),
        "focus_hit": sorted(list(focus_codes & set(circuit_codes))),
    }
    parts.append(
        "== circuit_hits ==\n"
        + dumps({"holdings_hit": len(circuit_hits["holdings_hit"]), "focus_hit": len(circuit_hits["focus_hit"]), **circuit_hits})
    )

    # 4) compliance lists (compact json)
    parts.append("== compliance ==\n" + dumps(compliance))

    # 5) holdings table csv
    parts.append("== holdings_table ==\n" + to_csv(holdings_rows, ["code", "shares", "avg_cost", "mkt_price", "pnl_pct"]))

    # broad market momentum (top 10 gainers/losers) as CSV
    parts.append("== top_gainers ==\n" + to_csv(build_momentum_rows(gainers_obj, 10), ["code", "pct_change", "value_mn"]))
    parts.append("== top_losers ==\n" + to_csv(build_momentum_rows(losers_obj, 10), ["code", "pct_change", "value_mn"]))

    # 6) focus table csv
    parts.append("== focus_table ==\n" + to_csv(focus_rows, ["code", "ltp", "ycp", "pct_change", "value_mn", "volume"]))
    if missing_focus:
        parts.append("== focus_missing_codes ==\n" + dumps(sorted(missing_focus)))

    # shortlist sources is useful for planner but can stay compact json
    parts.append("== shortlist ==\n" + dumps(shortlist))

    out_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
