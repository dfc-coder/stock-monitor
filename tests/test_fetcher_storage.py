from __future__ import annotations

from datetime import date
from typing import Any, List

import pytest

from data.fetcher import store_daily_closes
from data.models import Ticker, DailyPrice


class FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class FakeAsyncSession:
    """A minimal AsyncSession stub for unit testing store_daily_closes.

    Behavior:
    - execute(): returns queued FakeResult values in order.
    - add(): collects ORM objects to `added` list.
    - flush(): assigns incremental ids to Ticker objects without id.
    - commit()/close(): async no-ops for compatibility with context manager usage.
    """

    def __init__(self, execute_queue: List[FakeResult] | None = None) -> None:
        self.execute_queue: List[FakeResult] = execute_queue or []
        self.added: list[Any] = []
        self._next_id = 1

    async def execute(self, *args: Any, **kwargs: Any) -> FakeResult:
        if not self.execute_queue:
            return FakeResult(None)
        return self.execute_queue.pop(0)

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        # Assign ids to any Ticker without id yet
        for obj in self.added:
            if isinstance(obj, Ticker) and getattr(obj, "id", None) is None:
                setattr(obj, "id", self._next_id)
                self._next_id += 1

    async def commit(self) -> None:  # pragma: no cover - compatibility only
        return None

    async def rollback(self) -> None:  # pragma: no cover - compatibility only
        return None

    async def close(self) -> None:  # pragma: no cover - compatibility only
        return None


@pytest.mark.asyncio
async def test_store_daily_closes_inserts_new_prices_and_creates_tickers() -> None:
    # For two symbols, sequence of execute() calls per symbol:
    # 1) _get_or_create_ticker -> returns None (ticker not found)
    # 2) _get_daily_price -> returns None (no daily price yet)
    session = FakeAsyncSession(
        execute_queue=[
            # For AAPL
            FakeResult(None),  # ticker not found
            FakeResult(None),  # daily price not found
            # For MSFT
            FakeResult(None),  # ticker not found
            FakeResult(None),  # daily price not found
        ]
    )

    inserted = await store_daily_closes(session, {"AAPL": 110.0, "MSFT": 210.0}, date(2024, 1, 2))
    assert inserted == 2

    # Verify that two Ticker and two DailyPrice instances were added
    tickers = [o for o in session.added if isinstance(o, Ticker)]
    prices = [o for o in session.added if isinstance(o, DailyPrice)]

    assert {t.symbol for t in tickers} == {"AAPL", "MSFT"}
    assert len(prices) == 2
    # open/high/low/close equal to the provided close value
    for p in prices:
        assert p.open == p.close == p.high == p.low


@pytest.mark.asyncio
async def test_store_daily_closes_skips_existing_daily_price() -> None:
    # First symbol exists and has daily price already; second is new
    # Sequence:
    # AAPL: ticker exists -> return a Ticker; daily price exists -> return instance
    # MSFT: ticker missing -> None; daily price missing -> None
    existing_ticker = Ticker(symbol="AAPL")
    setattr(existing_ticker, "id", 42)
    existing_price = DailyPrice(
        ticker_id=42,
        price_date=date(2024, 1, 2),
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=0,
    )

    session = FakeAsyncSession(
        execute_queue=[
            FakeResult(existing_ticker),  # AAPL ticker exists
            FakeResult(existing_price),   # AAPL daily price exists
            FakeResult(None),             # MSFT ticker not found
            FakeResult(None),             # MSFT daily price not found
        ]
    )

    inserted = await store_daily_closes(session, {"AAPL": 100.0, "MSFT": 200.0}, date(2024, 1, 2))
    assert inserted == 1  # only MSFT inserted


@pytest.mark.asyncio
async def test_store_daily_closes_empty_input() -> None:
    session = FakeAsyncSession()
    inserted = await store_daily_closes(session, {}, date(2024, 1, 2))
    assert inserted == 0
