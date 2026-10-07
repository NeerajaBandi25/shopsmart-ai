# 19. Recommendation ranking

## What and why

ShopSmart ranks catalog products with a versioned, deterministic service. The model can explain the resulting evidence; it cannot declare a product “best” by itself. This makes mission changes and constraint decisions reproducible.

## Flow and files

`ShoppingMission` carries hard constraints separately from soft preferences. `recommendation_ranking.py` first excludes inactive, unavailable, wrong-category, over-budget, excluded-brand and attribute-incompatible products. Missing evidence for a required attribute also excludes a product. Eligible candidates receive normalized workload, preference, value and explicitly authorized personalization scores. A small brand-diversity adjustment is applied after choosing the best fit. The result carries ranked IDs, scores, tradeoffs, labels, and field-level catalog evidence.

## Data and authority

Prices, stock, product IDs and specification evidence originate in the ShopSmart database. Attribute weights and ranking version are included in the structured result. Recommendations do not claim a specification that the catalog does not support. If no candidates satisfy hard constraints, the service returns separately labeled alternatives and the exact violated constraints. Choosing an alternative requires a fresh user decision.

## Failure, tests and debugging

Unparseable numeric attributes remain unknown. Ranking fails closed for required constraints. Run `pytest tests/unit/test_recommendation_ranking.py` and `python -m src.evals.recommendation_eval` against the isolated factory review DB. Inspect mission filters, product specifications and the returned evidence when a candidate is omitted.

## Interview explanation

“The language model interprets the goal, but a deterministic backend enforces requirements and ranks verified candidates. A recommendation is explainable as catalog fields, weighted scores and explicit tradeoffs.”
