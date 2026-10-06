"""Versioned guardrails and optional Redis cache for typed intent, never commerce facts."""

import hashlib
import json
import re

from redis.exceptions import RedisError

from src.core.redis_client import get_redis_client

PROMPT_VERSION = "shopping-tools-v2"
GUARDRAIL_VERSION = "commerce-authority-v2"
MISSION_PROMPT_VERSION = "shopping-mission-v1"
RANKING_VERSION = "recommendation-ranker-v1"
RAG_VERSION = "policy-rag-v1"
ROUTING_POLICY_VERSION = "adaptive-free-routing-v1"
MISSION_CACHE_TTL = 300


def input_violation(text: str) -> bool:
    return bool(
        re.search(
            r"(?:ignore|override|bypass)\s+(?:all\s+)?(?:previous|system|safety|authentication|ownership)|"
            r"(?:reveal|print|show|give)\s+(?:me\s+)?(?:the\s+)?(?:system prompt|(?:openrouter\s+)?api key|secret|password)|"
            r"(?:execute|run)\s+(?:arbitrary\s+)?sql|(?:another|other)\s+(?:user'?s?|shopper'?s?)\s+(?:orders?|cart)",
            text,
            re.I,
        )
    )


class MissionRuntimeCache:
    """Cache non-authoritative extraction with scoped hashed keys and bounded TTL."""

    async def extract(self, owner_id, question, previous, extractor):
        key_data = json.dumps([str(owner_id), question, previous], sort_keys=True, default=str)
        key = "shopsmart:ai:mission:v2:" + hashlib.sha256(key_data.encode()).hexdigest()
        client = get_redis_client()
        if client:
            try:
                payload = await client.get(key)
                if payload:
                    from src.services.shopping_mission import ShoppingMission

                    cached = ShoppingMission.model_validate_json(payload)
                    cached.user_goal = question[:1000]
                    return cached, "HIT"
            except (RedisError, ValueError, TypeError):
                pass
        mission = extractor(question, previous)
        if client:
            try:
                await client.set(
                    key, mission.model_dump_json(exclude={"user_goal"}), ex=MISSION_CACHE_TTL
                )
            except (RedisError, TypeError, ValueError):
                return mission, "UNAVAILABLE"
        return mission, "MISS" if client else "DISABLED"
