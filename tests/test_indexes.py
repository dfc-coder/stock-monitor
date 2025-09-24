from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Make src importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from data.models import Base  # noqa: E402


async def _setup_sqlite_in_memory() -> tuple[async_sessionmaker[AsyncSession], callable]:
    """Create an async SQLite in-memory DB and return session factory and teardown."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async def _teardown() -> None:
        await engine.dispose()

    return session_factory, _teardown


@pytest.mark.asyncio
async def test_indexes_and_constraints_exist() -> None:
    session_factory, teardown = await _setup_sqlite_in_memory()
    try:
        async with session_factory() as session:
            # Open an async connection and use run_sync to access sync inspector APIs
            async with session.bind.connect() as async_conn:  # type: ignore[union-attr]
                def _collect_metadata(conn):
                    insp = inspect(conn)
                    return {
                        "daily_indexes": insp.get_indexes("daily_prices"),
                        "unique_constraints": insp.get_unique_constraints("daily_prices"),
                        "tickers_indexes": insp.get_indexes("tickers"),
                    }

                meta = await async_conn.run_sync(_collect_metadata)

            # Validate daily_prices index
            daily_index_names = {ix.get("name") for ix in meta["daily_indexes"]}
            assert "ix_daily_price_ticker_date" in daily_index_names

            # Validate daily_prices unique constraint
            uc = {
                uc_item.get("name"): tuple(uc_item.get("column_names", []))
                for uc_item in meta["unique_constraints"]
            }
            assert "uq_daily_price_ticker_date" in uc
            assert uc["uq_daily_price_ticker_date"] == ("ticker_id", "price_date")

            # Validate tickers has an index on symbol
            # SQLite auto-generates names sometimes; check by columns
            cols_by_index = {tuple(ix.get("column_names", [])) for ix in meta["tickers_indexes"]}
            assert ("symbol",) in cols_by_index
    finally:
        await teardown()
