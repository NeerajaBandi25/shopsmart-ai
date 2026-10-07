# 22. AI evaluations

## What and why

Versioned evaluation sets catch regressions in deterministic intent, hard constraints, rankings, retrieval, citations and adversarial behavior. Objective invariants use code checks, not a language-model judge.

## Flow and files

`evals/datasets/` stores golden retrieval, commerce, mission, ranking and local knowledge scenarios. `src/evals/runner.py` exercises retrieval and checks source ownership, answerability, citation membership and injection. `shopping_mission_eval.py` measures extraction, route and clarification. `recommendation_eval.py` checks seeded catalog results, constraint satisfaction, evidence and ranking stability. Baselines treat leakage as an upper bound and fail if a required measurement is missing.

## Metrics and limits

Results report case counts and per-invariant rates; deterministic safety thresholds are 100%. Ranking utility labels need explicit adjudicated product judgments before a relevance score can be claimed. Local deterministic results do not demonstrate a hosted-model SLA. Provider comparisons report latency, token usage, failures and available cost without inventing missing prices.

## How to run and debug

Run `python -m src.evals.shopping_mission_eval`, `python -m src.evals.runner` and `python -m src.evals.recommendation_eval` against the isolated local review database. Save reviewed JSON output in `docs/production-review/`. Investigate case-level failures before updating any threshold.

## Interview explanation

“We gate deterministic safety with exact checks and use a versioned golden set to quantify the rest. A missing metric or leakage regression fails closed.”
