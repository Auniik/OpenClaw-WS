# alert-monitor (holdings-only, stateful)

Runs every ~30 minutes during market hours and sends a Telegram alert **only** when:
- a holdings symbol hits upper/lower circuit (critical)
- a holdings symbol appears in risk-screen (critical)
- a holdings symbol appears in compliance non-submission (critical)
- a holdings symbol appears in delayed submission (warning; notify-on-change only)

Statefulness:
- Critical alerts repeat every `repeatMinutes` while still present.
- Warnings notify only when newly appearing since last run.

Artifacts/state live under workspace state root:
- runs: `state/dse-trading/YYYY-MM-DD/alert-monitor/`
- state: `state/dse-trading/alert-monitor/state.json`

Entry point:
- `monitor.py` prints either `NO_ALERT` or a Telegram-ready alert message.
