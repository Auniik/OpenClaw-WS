# market-open (planner + fetcher + analyst)

Mirrors `pre-market/` and `market-close/` deterministic pipeline.

Goal: ~40 minutes after market open, produce a short actionable pulse + plan:
- market breadth/turnover/index snapshot
- early leaders/laggards (value/volume/change)
- holdings risk + immediate actions
- a short watchlist with non-hallucinated levels

Files:
- `bundler.py` → builds a minimal seed bundle (sections)
- `enrich.py` → reads planner JSON + seed and produces enriched bundle with company + history
- `runner.py` → deterministic paths under `state/dse-trading/YYYY-MM-DD/market-open/`

Prompts:
- `prompts/market-open/planner.md` → outputs fetch plan JSON only
- `prompts/market-open/analyst.md` → final market-open report from enriched bundle

Intended cron flow (single isolated agentTurn):
1) `python3 runner.py` (writes paths.json + bundle-seed.txt)
2) LLM planner: read seed + `planner.md` → write `plan.json`
3) `python3 enrich.py --seed <seed> --plan <plan.json> --out <bundle>`
4) LLM analyst: read enriched bundle + `analyst.md` → write `ai-output.md`
