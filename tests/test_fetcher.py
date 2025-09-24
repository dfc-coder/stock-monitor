from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from data.fetcher import YFinanceFetcher, FetchError


def _install_fake_yfinance(download_impl: Any) -> None:
    """Install a lightweight fake 'yfinance' module into sys.modules."""
    fake_mod = types.ModuleType("yfinance")
    setattr(fake_mod, "download", download_impl)
    sys.modules["yfinance"] = fake_mod


def test_fetcher_returns_prices_and_uses_cache() -> None:
    calls: dict[str, int] = {"count": 0}

    def fake_download(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls["count"] += 1
        return {
            "AAPL": {"Close": [100.0, 110.0]},
            "MSFT": {"Close": [200.0, 210.0]},
        }

    _install_fake_yfinance(fake_download)

    fetcher = YFinanceFetcher(cache_ttl_seconds=60.0)

    result1 = fetcher.fetch_last_close(["AAPL", "MSFT"])  # first call hits fake download
    assert result1 == {"AAPL": 110.0, "MSFT": 210.0}
    assert calls["count"] == 1

    # Second call within TTL should NOT call yfinance again
    result2 = fetcher.fetch_last_close(["AAPL", "MSFT"])  # cache
    assert result2 == {"AAPL": 110.0, "MSFT": 210.0}
    assert calls["count"] == 1


def test_fetcher_respects_max_tickers() -> None:
    fetcher = YFinanceFetcher()
    symbols = [f"T{i}" for i in range(101)]
    with pytest.raises(ValueError):
        fetcher.fetch_last_close(symbols)


def test_retry_logic_eventual_success() -> None:
    state = {"n": 0}

    def flaky_download(*args: Any, **kwargs: Any) -> dict[str, Any]:
        state["n"] += 1
        if state["n"] < 3:  # first two attempts fail
            raise RuntimeError("temporary error")
        return {"AAPL": {"Close": [1.0, 2.0]}}

    _install_fake_yfinance(flaky_download)

    fetcher = YFinanceFetcher(max_retries=3, base_backoff_seconds=0.0001, sleep_fn=lambda _: None)
    result = fetcher.fetch_last_close(["AAPL"])
    assert result == {"AAPL": 2.0}
    assert state["n"] == 3


def test_failure_after_retries() -> None:
    def always_fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network down")

    _install_fake_yfinance(always_fail)

    fetcher = YFinanceFetcher(max_retries=2, base_backoff_seconds=0.0001, sleep_fn=lambda _: None)
    with pytest.raises(FetchError):
        fetcher.fetch_last_close(["AAPL"])
