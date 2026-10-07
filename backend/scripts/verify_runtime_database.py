"""Verify the database identity loaded by the backend's active local settings."""

import asyncio

from sqlalchemy import text

from src.database import engine


async def main() -> None:
    async with engine.connect() as connection:
        database_name, database_role = (
            await connection.execute(text("SELECT current_database(), current_user"))
        ).one()
    if database_name != "shopsmart_portfolio" or database_role != "agentsuresh":
        raise SystemExit("Expected shopsmart_portfolio as agentsuresh; refusing local startup.")
    print(f"runtime_database={database_name} runtime_role={database_role}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
