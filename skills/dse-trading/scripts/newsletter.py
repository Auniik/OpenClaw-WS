#!/usr/bin/env python3
import subprocess
import json
import sys
from datetime import datetime, timedelta

today = datetime.now().strftime("%Y-%m-%d")
today = datetime.now().date() - timedelta(days=1)
today = today.strftime("%Y-%m-%d")


search_cmd = [
    "gog",
    "gmail",
    "search",
    "IDLCSL-Newsflash@idlc.com",
    "--account",
    "auniikq@gmail.com",
    "--json",
]

read_cmd = [
    "gog",
    "gmail",
    "get",
    "<thread_id>",
    "--account",
    "auniikq@gmail.com",
    "--json",
]

try:
    result = subprocess.run(search_cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
except Exception:
    sys.exit(1)

threads = data.get("threads") or []
today_thread_id = None
for t in threads:
    if (t.get("date") or "").startswith(today):
        today_thread_id = t.get("id", "")
        break

if today_thread_id:
    read_cmd[3] = today_thread_id
    try:
        result = subprocess.run(read_cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        print(data.get("body", ""))
    except Exception:
        sys.exit(1)
    sys.exit(0)

# not found
sys.exit(1)