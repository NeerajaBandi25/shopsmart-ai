"""Publish a curated ShopSmart knowledge source into the backend-owned corpus."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.services.assistant_knowledge import KnowledgeIngestionService


async def run_publish(
    source_file: Path,
    apply: bool,
    allow_publish: str | None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    if not apply or allow_publish != "true":
        print(
            "Knowledge publishing refused; no changes made. Pass --apply and set "
            "SHOPSMART_ALLOW_KNOWLEDGE_PUBLISH=true."
        )
        return 2
    try:
        payload = json.loads(source_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("knowledge source must be a JSON object")
        if session_factory is None:
            from src.database import AsyncSessionLocal

            session_factory = AsyncSessionLocal
        async with session_factory() as session:
            source_id = await KnowledgeIngestionService(session).publish(
                source_key=payload["source_key"],
                title=payload["title"],
                category=payload["category"],
                content=payload["content"],
            )
    except Exception as error:
        print(
            f"Knowledge publishing failed ({type(error).__name__}); source content and "
            "connection details were suppressed.",
            file=sys.stderr,
        )
        return 1
    print(f"Published ShopSmart knowledge source {source_id}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_file", type=Path, help="curated JSON file stored server-side")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    return asyncio.run(
        run_publish(
            args.source_file,
            args.apply,
            os.environ.get("SHOPSMART_ALLOW_KNOWLEDGE_PUBLISH"),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
