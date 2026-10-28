import asyncio
import sys

from app.core.logging import configure_logging
from app.db.session import AsyncSessionFactory
from app.services.profiles import seed_profiles


async def main(command: str) -> None:
    if command != "seed":
        raise SystemExit(f"unknown command: {command}")
    async with AsyncSessionFactory() as session:
        await seed_profiles(session)


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seed"))
