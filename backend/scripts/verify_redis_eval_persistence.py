"""One-shot host check for ShopSmart adaptive evaluation-score persistence.

Run from backend/ with the project's .venv. This writes one unique temporary
score through ModelRuntimeState, verifies it through a fresh Python process and
the adaptive router, then deletes only that exact key. Its one-day TTL is an
additional cleanup bound if the process is forcibly terminated.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import uuid4

from src.core.config import settings
from src.core.redis_client import close_redis_client, get_redis_client
from src.services.adaptive_model_router import (
    AdaptiveFreeModelRouter,
    ModelCandidate,
    ModelRuntimeState,
)

TASK_TYPE = "PRODUCT_SEARCH"
TASK_KEY = "product_search"
EVAL_SCORE = 0.731
EVAL_SCORE_TTL_SECONDS = 86_400


def _validate_runtime_configuration() -> None:
    if not settings.redis_url:
        raise RuntimeError("ShopSmart REDIS_URL is not configured")
    parsed = urlsplit(settings.redis_url)
    database = (parsed.path or "/0").lstrip("/") or "0"
    if parsed.scheme not in {"redis", "rediss"}:
        raise RuntimeError("ShopSmart Redis URL must use redis or rediss")
    if parsed.hostname != "127.0.0.1" or parsed.port not in {None, 6379}:
        raise RuntimeError("ShopSmart Redis URL must target the configured local host")
    if database != "15":
        raise RuntimeError("ShopSmart Redis URL must select application DB 15")
    print(f"redis_db={database}")


async def _read_and_route_in_fresh_process(model_id: str, task_type: str) -> dict:
    """Read the real Redis score and ask a fresh production router to rank it."""
    state = ModelRuntimeState()
    snapshot = await state.snapshot(model_id, task_type)

    previous_mode = settings.ai_model_routing_mode
    settings.ai_model_routing_mode = "ADAPTIVE_FREE"
    try:
        control_model = f"shopsmart-host-acceptance/unscored-{uuid4().hex}:free"
        router = AdaptiveFreeModelRouter(state=state, api_key="host-acceptance-check")
        router._catalog = (
            ModelCandidate(model_id, frozenset({"tools", "tool_choice"})),
            ModelCandidate(control_model, frozenset({"tools", "tool_choice"})),
        )
        router._catalog_expires_at = time.monotonic() + 60
        selection = await router.select(task_type, streaming_required=False)
    finally:
        settings.ai_model_routing_mode = previous_mode

    factors = {item[0]: item[1:] for item in selection.score_factors}
    return {
        "read_score": snapshot["eval_score"],
        "router_selected_model": selection.selected_model,
        "router_eval_score": factors.get(model_id, (None,))[0],
    }


async def _child(model_id: str, task_type: str) -> int:
    try:
        _validate_runtime_configuration()
        result = await _read_and_route_in_fresh_process(model_id, task_type)
        print(json.dumps(result, separators=(",", ":")))
        if result["read_score"] != EVAL_SCORE:
            return 2
        if result["router_eval_score"] != EVAL_SCORE:
            return 3
        if result["router_selected_model"] != model_id:
            return 4
        return 0
    except Exception as exc:  # Never echo configuration or connection details.
        print(json.dumps({"error_type": type(exc).__name__}, separators=(",", ":")))
        return 1
    finally:
        await close_redis_client()


async def _parent() -> int:
    _validate_runtime_configuration()
    model_id = f"shopsmart-host-acceptance/{uuid4().hex}:free"
    redis_key = f"ai:model:{model_id}:eval_score:{TASK_KEY}"
    client = get_redis_client()
    if client is None:
        raise RuntimeError("ShopSmart Redis adapter did not create a client")

    key_written = False
    try:
        await ModelRuntimeState().record_eval(model_id, TASK_TYPE, EVAL_SCORE)
        key_written = True

        raw_value = await client.get(redis_key)
        if raw_value is None:
            raise RuntimeError("ShopSmart eval score was not readable from Redis")
        stored_score = float(raw_value)
        ttl = await client.ttl(redis_key)
        if stored_score != EVAL_SCORE:
            raise RuntimeError("Persisted ShopSmart eval score did not match the submitted score")
        if not 0 < ttl <= EVAL_SCORE_TTL_SECONDS:
            raise RuntimeError("Persisted ShopSmart eval score has no valid TTL")

        print(f"key={redis_key}")
        print(f"value={raw_value}")
        print(f"ttl_seconds={ttl}")

        child = subprocess.run(
            [sys.executable, __file__, "--child", model_id, TASK_TYPE],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=os.environ.copy(),
        )
        if child.returncode != 0:
            try:
                child_result = json.loads(child.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError):
                child_result = {"error_type": "FreshProcessVerificationError"}
            print("fresh_process=" + json.dumps(child_result, separators=(",", ":")))
            return child.returncode

        child_result = json.loads(child.stdout.strip().splitlines()[-1])
        print("fresh_process=" + json.dumps(child_result, separators=(",", ":")))
        print("fresh_router_consumed_score=PASS")
        return 0
    finally:
        if key_written:
            try:
                await client.delete(redis_key)
                print("cleanup=temporary_eval_key_deleted")
            except Exception as exc:
                print("cleanup_error_type=" + type(exc).__name__)
        await close_redis_client()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", nargs=2, metavar=("MODEL_ID", "TASK_TYPE"))
    args = parser.parse_args()
    if args.child:
        return asyncio.run(_child(*args.child))
    try:
        return asyncio.run(_parent())
    except Exception as exc:
        print("acceptance_error_type=" + type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
