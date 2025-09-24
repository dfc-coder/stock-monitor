from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data.models import Base, DailyPrice, Ticker
from data.fetcher import store_daily_closes


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
async def test_store_daily_closes_inserts_and_creates_ticker() -> None:
    session_factory, teardown = await _setup_sqlite_in_memory()
    try:
        async with session_factory() as session:
            # Arrange
            prices = {"AAPL": 123.45}
            d = date(2024, 1, 2)

            # Act
            inserted_count = await store_daily_closes(session, prices, d)
            await session.commit()

            # Assert
            assert inserted_count == 1

            # Ticker exists
            tickers = (await session.execute(select(Ticker))).scalars().all()
            assert len(tickers) == 1
            assert tickers[0].symbol == "AAPL"

            # DailyPrice exists with OHLC set to close and volume 0
            dp = (
                await session.execute(select(DailyPrice).where(DailyPrice.ticker_id == tickers[0].id))
            ).scalars().one()
            assert dp.price_date == d
            assert dp.open == pytest.approx(123.45)
            assert dp.high == pytest.approx(123.45)
            assert dp.low == pytest.approx(123.45)
            assert dp.close == pytest.approx(123.45)
            assert dp.volume == 0
    finally:
        await teardown()


@pytest.mark.asyncio
async def test_store_daily_closes_idempotent_for_same_date() -> None:
    session_factory, teardown = await _setup_sqlite_in_memory()
    try:
        async with session_factory() as session:
            prices = {"MSFT": 210.0}
            d = date(2024, 1, 3)

            inserted1 = await store_daily_closes(session, prices, d)
            inserted2 = await store_daily_closes(session, prices, d)
            await session.commit()

            # First call inserts, second should not duplicate
            assert inserted1 == 1
            assert inserted2 == 0

            # Validate only one DailyPrice row exists
            ticker = (
                await session.execute(select(Ticker).where(Ticker.symbol == "MSFT"))
            ).scalars().one()
            all_dp = (
                await session.execute(
                    select(DailyPrice).where(
                        (DailyPrice.ticker_id == ticker.id) & (DailyPrice.price_date == d)
                    )
                )
            ).scalars().all()
            assert len(all_dp) == 1
    finally:
        await teardown()
