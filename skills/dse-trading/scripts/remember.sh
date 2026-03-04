#!/usr/bin/env bash
set -euo pipefail

# Append a short markdown snippet to today's OpenClaw daily memory file.
# Usage:
#   echo "..." | append-memory.sh "Section title"

TITLE="${1:-DSE Trading}"

MEM_DIR="$HOME/.openclaw/workspace/memory"
mkdir -p "$MEM_DIR"

DAY="$(date +%Y-%m-%d)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
OUT="$MEM_DIR/$DAY.md"

{
  echo ""
  echo "## ${TITLE} (${DAY})"
  echo "- timestamp_utc: ${TS}"
  cat
  echo ""
} >>"$OUT"

printf "Appended to %s\n" "$OUT" >&2
