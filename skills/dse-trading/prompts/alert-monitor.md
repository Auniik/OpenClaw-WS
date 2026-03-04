# Prompt: alert-monitor

## Task
Run:
```bash
bash ~/.openclaw/workspace/skills/dse-trading/scripts/alert-monitor.sh
```

## Behavior
Be quiet unless something is important.

Only announce if any of these are true:
- a holding appears in risk-screen
- a holding appears in circuit (especially circuit down)
- unusual large block trade activity for a holding (if portfolio present)

If nothing triggers, respond with ONLY: NO_REPLY

If announcing, include a short bullet alert with riskAlerts 

## Memory logging (only when triggered)
When you announce (i.e., a trigger fired), also append a short alert note to daily memory:

```bash
printf "%s\n" "- alert: <what happened>" \
  "- action: <what to do>" \
  "- artifacts: <dataDir>" \
| bash ~/.openclaw/workspace/skills/dse-trading/scripts/remember.sh "DSE alert"
```
