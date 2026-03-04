# Prompt: pre-market planner

You are planning which additional DSE data to fetch (via dse-ai) so the analyst can produce a solid, non-hallucinated **pre-market** plan.

## Input
You will be given a **seed bundle** with these key sections:
- meta (JSON) — includes run_date + asof_date
- market_stats (JSON)
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
    "excluded": {"risk_screen": ["CODE"], "compliance": ["CODE"], "circuit": ["CODE"]},
    "reasons": {"CODE": ["reason", "reason"]}
  }
}

## Rules
- Use `meta.asof_date` as the plan `date` unless you have a strong reason not to.
- Watchlist max 7 symbols.
- **Hard exclude** from watchlist:
  - any code in risk-screen list
  - any code in compliance.non_submission
  - any code in circuit_hit_codes (currently hitting upper/lower circuit)
- `circuit_limits_codes` is the broad circuit-breaker universe; **do NOT** treat it as a hard exclusion by itself.
- Delayed submission is a warning signal (avoid unless extremely liquid/strong + you explain why).
- Prefer liquid + strong names from:
  - holdings
  - top_value / top_volume movers implied by shortlist sources
  - top_gainers (only if not risk/compliance/circuit)
- Always set includeHoldings=true.
- fetch.symbols should include:
  - all watchlist symbols
  - plus holdings (because morning decisions must consider existing exposure)
  - plus up to 0-5 additional symbols for comparison if needed

## What the analyst will need later
For every symbol in fetch.symbols, the fetcher will add:
- dse-ai company <CODE> --json
- dse-ai historical ... --inst <CODE> --json

So choose symbols that are worth that extra data.
