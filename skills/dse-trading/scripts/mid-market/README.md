# mid-market (planner + fetcher + analyst)

Deterministic pipeline like `pre-market/`, `market-open/`, and `market-close/`.

Goal: around mid-session, produce a short risk-management + opportunity check:
- market breadth/turnover/index snapshot (intraday)
- new circuit hits / compliance warnings
- portfolio actions (tighten/trim/exit/wait)
- a short watchlist with non-hallucinated levels

Files:
- `bundler.py` → seed bundle (intraday)
- `enrich.py` → company + historical enrichment + derived levels
- `runner.py` → deterministic paths under `state/dse-trading/YYYY-MM-DD/mid-market/`

Prompts:
- `prompts/mid-market/planner.md` → outputs fetch plan JSON only
- `prompts/mid-market/analyst.md` → final Telegram-friendly mid-market pulse
