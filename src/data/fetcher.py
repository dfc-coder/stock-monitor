"""
Data fetching utilities using yfinance with simple in-memory cache and retries.

Rules followed (generate-python-code):
- KISS/DRY: simple class with a single responsibility.
- Early return: guard invalid inputs.
- SOLID: dependency-free domain logic; IO via yfinance adapter usage.
- Type hints and docstrings.

Public API:
- YFinanceFetcher.fetch_last_close(symbols: list[str]) -> dict[str, float]

Notes:
- This module does not touch the database. It only fetches market data.
- Cache is in-memory and process-local with TTL. Suitable for the app process.
- yfinance is mocked in unit tests for speed and determinism.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List

from utils.config import Config


@dataclass(frozen=True)
class FetchResult:
    """DTO representing the last close price for a ticker symbol."""

    symbol: str
    last_close: float


class FetchError(RuntimeError):
    """Raised when fetching data ultimately fails after retries."""


class YFinanceFetcher:
    """Fetches market data for tickers using yfinance with cache and retries.

    Parameters
    - max_retries: number of attempts before failing (>= 1)
    - base_backoff_seconds: initial backoff for exponential strategy
    - cache_ttl_seconds: TTL for in-memory cache; values are reused within TTL
    - sleep_fn: injectable sleep function for testability
    """

    def __init__(
        self,
        *,
        max_retries: int = 3,
        base_backoff_seconds: float = 0.2,
        cache_ttl_seconds: float = 5.0,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        if base_backoff_seconds <= 0:
            raise ValueError("base_backoff_seconds must be > 0")
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds must be >= 0")

        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self._sleep = sleep_fn or time.sleep
        # cache: symbol -> (epoch_seconds, last_close)
        self._cache: Dict[str, tuple[float, float]] = {}

    def fetch_last_close(self, symbols: Iterable[str]) -> Dict[str, float]:
        """Return last close prices for the provided ticker symbols.

        - Respects Config.MAX_TICKERS.
        - Uses in-memory TTL cache to avoid redundant network calls.
        - Performs batch fetch with retries.
        """
        symbol_list: List[str] = [s.strip().upper() for s in symbols if s and s.strip()]
        if not symbol_list:
            return {}

        cfg = Config()  # read current environment; pure read-only
        if len(symbol_list) > cfg.MAX_TICKERS:
            raise ValueError(
                f"Too many tickers: {len(symbol_list)} > MAX_TICKERS={cfg.MAX_TICKERS}"
            )

        now = time.time()
        fresh: Dict[str, float] = {}
        to_fetch: List[str] = []
        for sym in symbol_list:
            cached = self._cache.get(sym)
            if cached and (now - cached[0]) <= self.cache_ttl_seconds:
                fresh[sym] = cached[1]
            else:
                to_fetch.append(sym)

        if not to_fetch:
            return fresh

        fetched = self._fetch_with_retries(to_fetch)
        # merge cache hits and newly fetched
        fresh.update(fetched)
        # update cache
        ts = time.time()
        for sym, price in fetched.items():
            self._cache[sym] = (ts, price)
        return fresh

    # Internal
    def _fetch_with_retries(self, symbols: List[str]) -> Dict[str, float]:
        last_error: Exception | None = None
        for attempt_index in range(1, self.max_retries + 1):
            try:
                return self._fetch_batch(symbols)
            except Exception as exc:  # noqa: BLE001 - we re-raise after retries
                last_error = exc
                if attempt_index == self.max_retries:
                    break
                sleep_seconds = self.base_backoff_seconds * (2 ** (attempt_index - 1))
                self._sleep(sleep_seconds)
        raise FetchError(str(last_error) if last_error else "unknown fetch error")

    def _fetch_batch(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch batch last close using yfinance.download.

        This function intentionally parses results defensively to avoid tight
        coupling with pandas structures during tests (tests will mock download).
        """
        # yfinance accepts space-separated tickers for batch download
        tickers = " ".join(symbols)
        # Lazy import to avoid requiring heavy dependencies during tests
        import yfinance as yf  # type: ignore

        data = yf.download(
            tickers=tickers,
            period="5d",  # use 5d to increase chance of at least one close
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=False,
            progress=False,
        )
        return self._parse_download_result(symbols, data)

    @staticmethod
    def _parse_download_result(expected_symbols: List[str], data: object) -> Dict[str, float]:
        """Extract last close price per symbol from yfinance.download result.

        Supports either of:
        - Mapping like {"AAPL": df_like}, where df_like has attribute/keys 'Close' and supports
          df_like["Close"][-1] (or .iloc[-1])
        - DataFrame with MultiIndex columns where ('Close', 'AAPL') exists; we try
          data[('Close', sym)][-1]
        """
        result: Dict[str, float] = {}

        # Case 1: mapping per symbol
        if isinstance(data, dict):  # type: ignore[unreachable]
            for sym in expected_symbols:
                df = data.get(sym)
                if df is None:
                    continue
                price = _extract_last_close_from_df_like(df)
                if price is not None:
                    result[sym] = float(price)
            return result

        # Case 2: generic object (e.g., pandas DataFrame)
        for sym in expected_symbols:
            price = None
            try:
                # try MultiIndex ('Close', sym)
                price = _safe_get_last(data, ("Close", sym))
            except Exception:
                price = None
            if price is None:
                try:
                    # try single column f"{sym} Close" or similar is uncommon; skip
                    pass
                except Exception:
                    price = None
            if price is not None:
                result[sym] = float(price)
        return result


def _extract_last_close_from_df_like(df_like: object) -> float | None:
    """Best-effort extraction of the last close value from a df-like object.

    Supports:
    - df_like["Close"].iloc[-1]
    - df_like["Close"][-1]
    """
    try:
        close_series = None
        if isinstance(df_like, dict):
            close_series = df_like.get("Close")
        else:
            # attribute or __getitem__
            try:
                close_series = df_like["Close"]  # type: ignore[index]
            except Exception:
                close_series = getattr(df_like, "Close", None)
        if close_series is None:
            return None
        try:
            return float(close_series.iloc[-1])  # type: ignore[attr-defined]
        except Exception:
            try:
                return float(close_series[-1])  # type: ignore[index]
            except Exception:
                return None
    except Exception:
        return None


def _safe_get_last(df_like: object, key: object) -> float | None:
    try:
        series = df_like[key]  # type: ignore[index]
        try:
            return float(series.iloc[-1])  # type: ignore[attr-defined]
        except Exception:
            return float(series[-1])  # type: ignore[index]
    except Exception:
        return None
