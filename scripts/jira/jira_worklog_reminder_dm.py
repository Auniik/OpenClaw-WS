#!/usr/bin/env python3
"""Team worklog reminder DM sender.

- Fetches each member's Jira WW tickets in status In Progress.
- For each ticket, reads time logged + estimate and computes remaining.
- Sends a Google Chat DM via `gog chat dm send <email> --text <msg> --no-input`.

Designed to be run from OpenClaw cron (or manually).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

JIRA_BASE = "https://portonics.atlassian.net/browse/"
DEFAULT_PROJECT = "WW"
DEFAULT_STATUS = "In Progress"
DEFAULT_MAX_TICKETS = 15


@dataclass
class Member:
    name: str
    email: str
    jira_assignee: str
    enabled: bool = True


def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)


def parse_issue_keys(search_output: str, project_key: str) -> List[str]:
    # jira-ai's table output may contain non-ASCII hyphen characters (e.g., U+2011),
    # which breaks a simple "WW-123" regex. Normalize common dash variants to '-'.
    normalized = search_output
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        normalized = normalized.replace(ch, "-")

    pat = re.compile(rf"{re.escape(project_key)}-\d+")
    seen = set()
    keys: List[str] = []
    for k in pat.findall(normalized):
        if k not in seen:
            seen.add(k)
            keys.append(k)
    return keys


def get_issue_summary(key: str) -> str:
    txt = run(["jira-ai", "issue", "get", key])
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", txt, re.M)
    return m.group(1).strip() if m else key


def parse_stats_row(key: str, stats_output: str) -> Tuple[str, str]:
    """Return (logged, estimate) strings as displayed by jira-ai."""
    for line in stats_output.splitlines():
        # Row starts with: "│ WW-2077" etc.
        if line.strip().startswith("│ " + key):
            parts = [p.strip() for p in line.split("│") if p.strip()]
            # Expected: [Key, Summary, Time Logged, Estimate, Status Breakdown]
            if len(parts) >= 4:
                return parts[2], parts[3]
    return "N/A", "N/A"


def to_minutes(s: str) -> Optional[int]:
    s = s.strip()
    if s in ("N/A", ""):
        return None
    if s == "0m":
        return 0

    total = 0
    # Jira time tracking often uses w/d/h/m. We assume:
    # 1d = 8h, 1w = 5d.
    for num, unit in re.findall(r"(\d+)\s*(w|d|h|m)", s):
        n = int(num)
        if unit == "m":
            total += n
        elif unit == "h":
            total += 60 * n
        elif unit == "d":
            total += 60 * 8 * n
        elif unit == "w":
            total += 60 * 8 * 5 * n
    return total


def fmt_minutes(mins: int) -> str:
    if mins <= 0:
        return "0m"
    h, m = divmod(mins, 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def build_message(
    member: Member,
    issues: List[Tuple[str, str, str, str, str]],
    project: str,
    status: str,
) -> str:
    # issues tuples: (key, summary, remaining, logged, estimated)
    # Google Chat sometimes collapses single newlines; using blank lines (double \n)
    # between sections tends to preserve visual separation.
    lines: List[str] = [
        "Daily worklog reminder: Your In Progress tickets:",
        "",
    ]

    if not issues:
        lines.append("(no In Progress tickets found)")
    else:
        # One line per ticket, with the URL inline so it's clickable.
        for i, (key, summary, remaining, logged, estimated) in enumerate(issues, start=1):
            lines.append(
                f"{i}. {key}: {summary} \n Rem: {remaining} | Log: {logged} | Est: {estimated} \n {JIRA_BASE}{key}"
            )
            # Blank line between tickets (double newline overall)
            lines.append("")

    lines.append("Goodnight.")
    return "\n".join(lines).rstrip() + "\n"


def send_dm(email: str, text: str) -> str:
    out = run(["gog", "chat", "dm", "send", email, "--text", text, "--no-input"])
    return out


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def members_from_config(cfg: Dict[str, Any]) -> List[Member]:
    members: List[Member] = []
    for m in cfg.get("members", []):
        members.append(
            Member(
                name=m["name"],
                email=m["email"],
                jira_assignee=m.get("jira_assignee", m["name"]),
                enabled=bool(m.get("enabled", True)),
            )
        )
    return members


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "team_config.json"),
        help="Path to unified team config JSON",
    )
    ap.add_argument("--dry-run", action="store_true", help="Do not send DMs")
    ap.add_argument("--member", action="append", help="Only run for member email (repeatable)")
    args = ap.parse_args()

    cfg = load_config(args.config)

    project = cfg.get("jira", {}).get("project", DEFAULT_PROJECT)
    status = cfg.get("worklog_reminder", {}).get("status", DEFAULT_STATUS)
    max_tickets = int(cfg.get("worklog_reminder", {}).get("max_tickets", DEFAULT_MAX_TICKETS))

    members = [m for m in members_from_config(cfg) if m.enabled]
    if args.member:
        allow = set(args.member)
        members = [m for m in members if m.email in allow]

    if not members:
        print("No enabled members to run.")
        return 0

    for member in members:
        # NOTE: We pass args as a list (no shell), so use plain quotes for JQL.
        jql = (
            f'project = {project} AND assignee = "{member.jira_assignee}" '
            f'AND status = "{status}" ORDER BY updated DESC'
        )

        search_out = run(["jira-ai", "issue", "search", jql])
        keys = parse_issue_keys(search_out, project)[:max_tickets]

        issues: List[Tuple[str, str, str, str, str]] = []
        for key in keys:
            summary = get_issue_summary(key)
            stats_out = run(["jira-ai", "issue", "stats", key])
            logged, estimated = parse_stats_row(key, stats_out)

            rem = "N/A"
            est_m = to_minutes(estimated)
            log_m = to_minutes(logged)
            if est_m is not None and log_m is not None:
                rem = fmt_minutes(est_m - log_m)

            issues.append((key, summary, rem, logged, estimated))

        msg = build_message(member, issues, project, status)

        if args.dry_run:
            print(f"--- DRY RUN: {member.name} <{member.email}> ---")
            print(msg)
            continue

        out = send_dm(member.email, msg)
        # Print the resource/thread lines for traceability
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
