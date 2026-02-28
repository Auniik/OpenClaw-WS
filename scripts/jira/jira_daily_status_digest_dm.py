#!/usr/bin/env python3
"""Team Jira update notifier (deterministic).

Goal:
- For each enabled member, DM them their own Jira update:
  Overdue / In Progress / To Do
- Additionally DM PM (Farin) a combined view for all enabled members.

Uses:
- jira-ai for JQL search + issue get
- gog chat for DMs

Scheduling target: 2:00 PM Mon–Fri Asia/Dhaka (via OpenClaw cron).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

JIRA_BASE = "https://portonics.atlassian.net/browse/"
DEFAULT_PROJECT = "WW"
DEFAULT_MAX = 10


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


def jql_search_keys(jql: str, project_key: str, max_items: int) -> List[str]:
    out = run(["jira-ai", "issue", "search", jql])
    return parse_issue_keys(out, project_key)[:max_items]


def build_section(title: str, keys: List[str]) -> List[str]:
    lines: List[str] = [f"{title}:" ]
    if not keys:
        lines.append("- none")
        return lines

    for i, k in enumerate(keys, start=1):
        summary = get_issue_summary(k)
        lines.append(f"{i}. {k}: {summary} {JIRA_BASE}{k}")
    return lines


def send_dm(email: str, text: str) -> str:
    return run(["gog", "chat", "dm", "send", email, "--text", text, "--no-input"])


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def members_from_config(cfg: Dict[str, Any]) -> Tuple[str, Optional[Member], List[Member]]:
    project = cfg.get("jira", {}).get("project", DEFAULT_PROJECT)

    pm_cfg = cfg.get("pm")
    pm: Optional[Member] = None
    if pm_cfg and pm_cfg.get("enabled", True):
        pm = Member(
            name=pm_cfg.get("name", "PM"),
            email=pm_cfg.get("email", ""),
            jira_assignee=pm_cfg.get("jira_assignee", pm_cfg.get("name", "PM")),
            enabled=True,
        )

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
    members = [m for m in members if m.enabled]
    return project, pm, members


def build_member_message(project: str, member: Member, max_items: int, inprog_status: str, todo_status: str) -> str:
    overdue_jql = (
        f'project = {project} AND assignee = "{member.jira_assignee}" '
        f'AND duedate < now() AND statusCategory != Done '
        f'ORDER BY duedate ASC'
    )
    inprog_jql = (
        f'project = {project} AND assignee = "{member.jira_assignee}" '
        f'AND status = "{inprog_status}" ORDER BY updated DESC'
    )
    todo_jql = (
        f'project = {project} AND assignee = "{member.jira_assignee}" '
        f'AND status = "{todo_status}" ORDER BY priority DESC, updated DESC'
    )

    overdue = jql_search_keys(overdue_jql, project, max_items)
    inprog = jql_search_keys(inprog_jql, project, max_items)
    todo = jql_search_keys(todo_jql, project, max_items)

    lines: List[str] = [
        f"Hi {member.name}, here is your jira update ({project})",
        "",
    ]
    lines += build_section("Overdue", overdue)
    lines.append("")
    lines += build_section("In Progress", inprog)
    lines.append("")
    lines += build_section("To Do", todo)

    return "\n".join(lines).rstrip() + "\n"


def build_pm_message(
    project: str,
    pm_name: str,
    members: List[Member],
    max_items: int,
    inprog_status: str,
    todo_status: str,
) -> str:
    lines: List[str] = [
        f"Hi {pm_name}, here is the team's Jira update of {project}",
        "",
    ]
    for member in members:
        lines.append(f"== {member.name} ==")
        # keep it lighter for PM: fewer items
        msg = build_member_message(project, member, max_items, inprog_status, todo_status)
        # strip the first line (header) of member message and reuse rest
        msg_lines = msg.splitlines()[2:]  # drop header + blank line
        lines.extend(msg_lines)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "team_config.json"),
        help="Path to unified team config JSON",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--member", action="append", help="Only run for member email (repeatable)")
    args = ap.parse_args()

    cfg = load_json(args.config)
    project, pm, members = members_from_config(cfg)

    max_items = int(cfg.get("daily_status_digest", {}).get("max_items", DEFAULT_MAX))
    inprog_status = cfg.get("daily_status_digest", {}).get("statuses", {}).get("in_progress", "In Progress")
    todo_status = cfg.get("daily_status_digest", {}).get("statuses", {}).get("todo", "To Do")

    pm_email = (pm.email if pm else "")
    pm_name = (pm.name if pm else "Farin")

    if args.member:
        allow = set(args.member)
        members = [m for m in members if m.email in allow]

    if not members:
        print("No enabled members to run.")
        return 0

    # 1) DM each member their own update
    for m in members:
        text = build_member_message(project, m, max_items, inprog_status, todo_status)
        if args.dry_run:
            print(f"--- DRY RUN: {m.name} <{m.email}> ---")
            print(text)
        else:
            out = send_dm(m.email, text)
            sys.stdout.write(out)
            if not out.endswith("\n"):
                sys.stdout.write("\n")

    # 2) DM PM the team snapshot
    if pm_email:
        text = build_pm_message(project, pm_name, members, max_items, inprog_status, todo_status)
        if args.dry_run:
            print(f"--- DRY RUN: {pm_name} <{pm_email}> ---")
            print(text)
        else:
            out = send_dm(pm_email, text)
            sys.stdout.write(out)
            if not out.endswith("\n"):
                sys.stdout.write("\n")
    else:
        print("PM email missing in team_config.json; skipping PM DM.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
