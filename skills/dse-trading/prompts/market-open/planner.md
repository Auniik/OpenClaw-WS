# Prompt: market-open planner

You are planning which additional DSE data to fetch (via dse-ai) so the analyst can produce a solid, non-hallucinated **market-open (40 min after open)** pulse + action plan.

## Input
You will be given a **seed bundle** with these key sections:
- meta (JSON)
- market_stats (JSON)
- market_overview (JSON)
- summary_recent (JSON)
- risk_screen_codes (JSON list)
- compliance (JSON)
- circuit_limits_codes + circuit_hit_codes + circuit_hits (JSON)
- holdings_table (CSV)
- top_gainers (CSV)
- top_losers (CSV)
- focus_table (CSV)
- shortlist (JSON)

Treat the bundle as the only source of truth.

## Output (STRICT)
Return **ONLY** a single-line JSON object (no markdown, no commentary).

Schema:
{
  "date": "YYYY-MM-DD",
  "historyDays": 60,
  "watchlist": ["CODE"],
  "fetch": {
    "symbols": ["CODE"],
    "includeHoldings": true
  },
  "notes": {
    "excluded": {"risk_screen": ["CODE"], "compliance": ["CODE"], "circuit_hit": ["CODE"]},
    "reasons": {"CODE": ["reason", "reason"]}
  }
}

## Rules
- Use `meta.asof_date` as the plan `date` unless you have a strong reason not to.
- Watchlist max **5** symbols (intraday focus).
- Always set includeHoldings=true.
- **Hard exclude** from watchlist:
  - any code in risk-screen list
  - any code in compliance.non_submission
  - any code in circuit_hit_codes (currently hitting upper/lower circuit)
- `circuit_limits_codes` is a broad universe; do NOT treat it as a hard exclusion by itself.
- Prefer liquid, actively traded names from:
  - holdings (for management / exits)
  - top_value/top_volume/top_change (from shortlist + focus_table)
- If market looks broadly weak (breadth very negative), bias the plan toward: fewer symbols, tighter stops, more “WAIT”.

## What the analyst will need later
For every symbol in fetch.symbols, the fetcher will add:
- dse-ai company <CODE> --json
- dse-ai historical ... --inst <CODE> --json

So choose symbols that are worth that extra data.
