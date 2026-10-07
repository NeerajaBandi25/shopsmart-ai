# 18. Shopping mission engine

## What and why

A shopping mission turns a message into typed commerce intent: category, use cases, workload priorities, budget, required attributes, soft preferences, urgency and a single optional clarification. Separating must-haves from ranking preferences prevents a “close match” from silently violating the shopper's limit.

## Flow and files

`shopping_mission.py` holds the strict Pydantic model and conservative deterministic extraction. A simple category-plus-price query can take `FAST_PATH`; a multi-constraint query takes `LLM_PATH`. The conversation stores the validated mission so later refinements such as “make it lighter” retain authorized constraints. Provider-derived soft understanding is validated and merged with server-extracted hard requirements.

## Data, safety and failure modes

Budgets use integer paise. A stretch price is a hard ceiling only where the shopper states permission to stretch; their preferred amount stays soft. Unknown categories and malformed bounds fail validation. One useful question is returned for an underspecified laptop mission. Provider output cannot alter ownership, authoritative price or explicit hard constraints. A missing provider returns the safe deterministic response.

## How to test and debug

Run `pytest tests/unit/test_shopping_mission.py` and `python -m src.evals.shopping_mission_eval`. The versioned dataset checks route accuracy, hard and preferred budget extraction, use cases, clarification and context retention. Inspect `execution_path`, `hard_constraints`, and `soft_constraints` in the typed result.

## Interview explanation

“We maintain structured state across turns, distinguish hard requirements from soft ranking signals, and ask one question only when missing intent changes the recommendation.”
