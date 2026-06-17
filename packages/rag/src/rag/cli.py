import asyncio

from fund_core.db import async_session_factory
from rag.ingest import ingest_research_dir


def main() -> None:
    async def _run() -> None:
        async with async_session_factory() as session:
            stats = await ingest_research_dir(session)
            print(f"Ingested: {stats}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
