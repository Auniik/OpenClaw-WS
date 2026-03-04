# pre-market (planner + fetcher + analyst)

Mirrors the `market-close/` deterministic pipeline.

Files:
- `bundler.py` → builds a minimal seed bundle (sections)
- `enrich.py` → reads planner JSON + seed and produces enriched bundle with company + history
- `runner.py` → deterministic paths under `state/dse-trading/YYYY-MM-DD/pre-market/`

Prompts:
- `prompts/pre-market/planner.md` → outputs fetch plan JSON only
- `prompts/pre-market/analyst.md` → final morning plan from enriched bundle

Intended cron flow (single isolated agentTurn):
1) `python3 runner.py` (writes paths.json + bundle-seed.txt)
2) LLM planner: read seed + `planner.md` → write `plan.json`
3) `python3 enrich.py --seed <seed> --plan <plan.json> --out <bundle>`
4) LLM analyst: read enriched bundle + `analyst.md` → write `ai-output.md`
