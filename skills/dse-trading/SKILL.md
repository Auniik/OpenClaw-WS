---
name: dse-trading
description: Deterministic DSE (Dhaka Stock Exchange) trading workflows using the local dse-ai CLI (planner → enrich → analyst) plus a holdings-only risk alert monitor.
metadata: {"openclaw":{"emoji":"📈","scope":"local","requires":{"bins":["dse-ai","python3"]}}}
---

# dse-trading

Deterministic, file-based DSE workflows. Each phase writes artifacts under a stable state root and produces a single `bundle.txt` for the LLM.

## State root

All runs write to:

- `~/.openclaw/workspace/state/dse-trading/YYYY-MM-DD/<phase>/...`

## Phases (deterministic pipelines)

Each phase uses:

1) `runner.py` → creates `<data_dir>` + `paths.json` + seed bundle
2) **Planner** prompt → outputs strict one-line JSON plan (`plan.json`)
3) `enrich.py` → fetches company + historical for planned symbols → writes `bundle.txt`
4) **Analyst** prompt → writes Telegram-ready `ai-output.md`

Implemented phases:
- `pre-market/`
- `market-open/` (includes newsletter brief step; see below)
- `mid-market/`
- `market-close/`
- `weekly-review/` (runner + bundler only; no planner/enrich)
- `monthly-review/` (runner + bundler only; no planner/enrich)

Scripts:
- `skills/dse-trading/scripts/<phase>/{runner.py,bundler.py,enrich.py}` (where applicable)
Prompts:
- `skills/dse-trading/prompts/<phase>/*.md`

## Newsletter (market-open)

- Fetch raw newsletter text:
  - `skills/dse-trading/scripts/newsletter.py`
- Brief it for planning:
  - `skills/dse-trading/prompts/market-open/newsletter-brief.md`

The market-open cron writes:
- `<data_dir>/newsletter.txt` (raw)
- `<data_dir>/newsletter-brief.txt` (short; used by planner)

## Risk alert monitor (holdings-only)

Rule-based (no LLM). Uses stateful suppression + repeat for critical alerts.

- Script: `skills/dse-trading/scripts/alert-monitor/monitor.py`
- State: `~/.openclaw/workspace/state/dse-trading/alert-monitor/state.json`

It prints either `NO_ALERT` or a Telegram-ready alert message.

## Helper

- `skills/dse-trading/scripts/remember.sh` — optional helper for writing critical alerts into workspace memory.
