#!/usr/bin/env python3
"""Holdings-only risk alert monitor for DSE.

Prints either:
- NO_ALERT
or
- a Telegram-ready alert message.

Designed to be run under OpenClaw cron (isolated) every ~30 minutes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")


def now_local() -> datetime:
    return datetime.now().astimezone()


def now_ts() -> int:
    return int(time.time())


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def run(cmd: list[str], timeout_s: int = 40) -> tuple[int, str]:
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


def json_from_output(out: str) -> dict:
    s = (out or "").strip()
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


def codes_from_circuit(obj: dict) -> list[str]:
    rows = None
    if isinstance(obj.get("data"), dict):
        rows = obj["data"].get("rows")
    if rows is None:
        rows = obj.get("rows")
    if not isinstance(rows, list):
        # fallback: search any list of dicts
        for v in obj.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                rows = v
                break
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        c = r.get("Trade Code") or r.get("TRADING CODE") or r.get("tradingCode") or r.get("code")
        if isinstance(c, str):
            code = c.strip()
            if CODE_RE.fullmatch(code) and code not in out:
                out.append(code)
    return sorted(out)


def codes_from_risk_screen(obj: dict) -> list[str]:
    threats = obj.get("threats")
    if not isinstance(threats, list):
        threats = obj.get("data")
    out: list[str] = []
    if isinstance(threats, list):
        for t in threats:
            if not isinstance(t, dict):
                continue
            c = t.get("tradingCode") or t.get("TRADING CODE") or t.get("Trade Code")
            if isinstance(c, str):
                code = c.strip()
                if CODE_RE.fullmatch(code) and code not in out:
                    out.append(code)
    return sorted(out)


def codes_from_compliance(obj: dict) -> list[str]:
    subs = obj.get("submissions")
    if not isinstance(subs, list):
        return []
    out: list[str] = []
    for s in subs:
        if not isinstance(s, dict):
            continue
        c = s.get("tradingCode") or s.get("TRADING CODE") or s.get("Trade Code")
        if isinstance(c, str):
            code = re.sub(r"\s*\*+\s*$", "", c.strip())
            if CODE_RE.fullmatch(code) and code not in out:
                out.append(code)
    return sorted(out)


def holdings_from_portfolio(obj: dict) -> list[str]:
    stocks = obj.get("stocks")
    if not isinstance(stocks, list):
        return []
    out: list[str] = []
    for r in stocks:
        if not isinstance(r, dict):
            continue
        c = r.get("symbol") or r.get("symbole")
        if isinstance(c, str):
            code = c.strip().upper()
            if CODE_RE.fullmatch(code) and code not in out:
                out.append(code)
    return sorted(out)


@dataclass
class MonitorConfig:
    state_root: Path
    dse_state_root: Path
    repeat_minutes: int = 75
    max_codes_per_line: int = 10


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, st: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(st) + "\n", encoding="utf-8")


def fmt_codes(codes: list[str], maxn: int) -> str:
    if not codes:
        return "(none)"
    s = ", ".join(codes[:maxn])
    if len(codes) > maxn:
        s += f" (+{len(codes) - maxn} more)"
    return s


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--state-root",
        default="/Users/anik/.openclaw/workspace/state/dse-trading",
        help="Workspace state root",
    )
    ap.add_argument("--repeat-minutes", type=int, default=75)
    args = ap.parse_args()

    cfg = MonitorConfig(
        state_root=Path(args.state_root),
        dse_state_root=Path(args.state_root),
        repeat_minutes=max(15, int(args.repeat_minutes)),
    )

    t0 = now_local()
    date_dir = t0.strftime("%Y-%m-%d")
    run_dir = cfg.dse_state_root / date_dir / "alert-monitor"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Fetch data
    rc_port, out_port = run(["dse-ai", "broker", "shanta", "portfolio", "--json"], timeout_s=120)
    portfolio = json_from_output(out_port) if rc_port == 0 else {}
    holdings = holdings_from_portfolio(portfolio)

    rc_upper, out_upper = run(["dse-ai", "circuit", "--upper", "--json"], timeout_s=40)
    rc_lower, out_lower = run(["dse-ai", "circuit", "--lower", "--json"], timeout_s=40)
    upper_codes = codes_from_circuit(json_from_output(out_upper) if rc_upper == 0 else {})
    lower_codes = codes_from_circuit(json_from_output(out_lower) if rc_lower == 0 else {})

    rc_risk, out_risk = run(["dse-ai", "risk-screen", "--json"], timeout_s=40)
    risk_codes = codes_from_risk_screen(json_from_output(out_risk) if rc_risk == 0 else {})

    rc_non, out_non = run(["dse-ai", "compliance", "--non-submitted", "--json"], timeout_s=40)
    rc_del, out_del = run(["dse-ai", "compliance", "--delayed", "--json"], timeout_s=40)
    non_codes = codes_from_compliance(json_from_output(out_non) if rc_non == 0 else {})
    del_codes = codes_from_compliance(json_from_output(out_del) if rc_del == 0 else {})

    hold_set = set(holdings)
    hold_upper = sorted(list(hold_set & set(upper_codes)))
    hold_lower = sorted(list(hold_set & set(lower_codes)))
    hold_risk = sorted(list(hold_set & set(risk_codes)))
    hold_non = sorted(list(hold_set & set(non_codes)))
    hold_del = sorted(list(hold_set & set(del_codes)))

    # State
    state_path = cfg.state_root / "alert-monitor" / "state.json"
    st = load_state(state_path)
    st.setdefault("last", {})
    st.setdefault("notified", {})

    repeat_s = cfg.repeat_minutes * 60
    now = now_ts()

    def due(type_key: str, codes: list[str], critical: bool) -> list[str]:
        # Returns codes that should be notified now.
        notified_map = st["notified"].setdefault(type_key, {})
        prev_codes = set(st["last"].get(type_key, []) or [])
        cur_codes = set(codes)

        out_due: list[str] = []

        if critical:
            for c in sorted(cur_codes):
                last_sent = int(notified_map.get(c, 0) or 0)
                if last_sent == 0 or (now - last_sent) >= repeat_s:
                    out_due.append(c)
        else:
            # warning: notify only on newly appearing
            for c in sorted(cur_codes - prev_codes):
                out_due.append(c)

        # Update last snapshot
        st["last"][type_key] = sorted(list(cur_codes))

        # Update notified timestamps for codes we will send now
        for c in out_due:
            notified_map[c] = now

        # Also clean notified map for codes that disappeared (optional hygiene)
        for c in list(notified_map.keys()):
            if c not in cur_codes and (now - int(notified_map.get(c, 0) or 0)) > 14 * 86400:
                notified_map.pop(c, None)

        return out_due

    due_upper = due("circuit_upper", hold_upper, critical=True)
    due_lower = due("circuit_lower", hold_lower, critical=True)
    due_risk = due("risk_screen", hold_risk, critical=True)
    due_non = due("compliance_non", hold_non, critical=True)
    due_del = due("compliance_delayed", hold_del, critical=False)

    # Save run artifact
    artifact = {
        "ts": t0.isoformat(),
        "holdings": holdings,
        "hits": {
            "circuit_upper": hold_upper,
            "circuit_lower": hold_lower,
            "risk_screen": hold_risk,
            "compliance_non": hold_non,
            "compliance_delayed": hold_del,
        },
        "due": {
            "circuit_upper": due_upper,
            "circuit_lower": due_lower,
            "risk_screen": due_risk,
            "compliance_non": due_non,
            "compliance_delayed": due_del,
        },
        "rc": {
            "portfolio": rc_port,
            "circuit_upper": rc_upper,
            "circuit_lower": rc_lower,
            "risk": rc_risk,
            "non": rc_non,
            "delayed": rc_del,
        },
    }

    (run_dir / f"run-{t0.strftime('%H%M%S')}.json").write_text(dumps(artifact) + "\n", encoding="utf-8")

    # Decide alert
    any_due = bool(due_upper or due_lower or due_risk or due_non or due_del)
    if not any_due:
        save_state(state_path, st)
        print("NO_ALERT")
        return

    # Compose message
    hhmm = t0.strftime("%H:%M")
    lines: list[str] = []
    lines.append(f"DSE Risk Alert ({hhmm})")

    if due_upper:
        lines.append(f"- HOLDINGS upper circuit: {fmt_codes(due_upper, 8)}")
    if due_lower:
        lines.append(f"- HOLDINGS lower circuit: {fmt_codes(due_lower, 8)}")
    if due_risk:
        lines.append(f"- HOLDINGS risk-screen: {fmt_codes(due_risk, 10)}")
    if due_non:
        lines.append(f"- HOLDINGS compliance non-submission: {fmt_codes(due_non, 10)}")
    if due_del:
        lines.append(f"- HOLDINGS delayed submission (new): {fmt_codes(due_del, 10)}")

    # Short action guidance
    actions: list[str] = []
    if due_lower or due_upper:
        actions.append("Avoid adding; tighten stops / consider partial exit on liquidity.")
    if due_risk:
        actions.append("High risk-screen flag: plan exit; do not average down.")
    if due_non:
        actions.append("Compliance non-submission: no new buys; consider reducing exposure.")
    if due_del and not (due_lower or due_upper or due_risk or due_non):
        actions.append("Governance warning: keep size small and stops tight.")

    if actions:
        lines.append("Action")
        for a in actions[:3]:
            lines.append(f"- {a}")

    lines.append(f"Artifacts: {run_dir}")

    save_state(state_path, st)
    print("\n".join(lines).strip())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
