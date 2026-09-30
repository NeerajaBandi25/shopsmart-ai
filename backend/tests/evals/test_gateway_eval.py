from src.evals.gateway_eval import evaluate_routing


def test_provider_routing_eval_is_reproducible():
    result = evaluate_routing()
    assert result["case_count"] == 3
    assert result["pass_rate"] == 1.0
