# market-close (planner + fetcher + analyst)

Files:
- `bundler.py` → builds a minimal seed bundle (JSON sections)
- `enrich.py` → reads planner JSON + seed bundle and produces an enriched bundle with company + historical

Prompts:
- `prompts/market-close/planner.md` → outputs fetch plan JSON only
- `prompts/market-close/analyst.md` → final close report from enriched bundle

Intended cron flow (single isolated agentTurn):
1) `python3 bundler.py --out <seed>`
2) LLM planner: read seed + `planner.md` → write `<plan.json>`
3) `python3 enrich.py --seed <seed> --plan <plan.json> --out <bundle>`
4) LLM analyst: read enriched bundle + `analyst.md` → write `ai-output.md`
