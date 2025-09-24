"""
SQLAlchemy ORM models for the application domain.

Defines:
- Ticker: stock symbol master data (unique symbol)
- DailyPrice: OHLCV daily price per ticker with unique (ticker_id, date)

Notes
- Pure ORM mapping (no IO). DB connection lives in adapters (db/connection.py).
- Compatible with SQLAlchemy 2.0 style.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class Ticker(Base):
    """Represents a stock ticker symbol (e.g., AAPL)."""

    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    prices: Mapped[List[DailyPrice]] = relationship(
        back_populates="ticker",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Ticker(id={self.id!r}, symbol={self.symbol!r})"


class DailyPrice(Base):
    """Represents a daily OHLCV price for a given ticker and date."""

    __tablename__ = "daily_prices"
    __table_args__ = (
        UniqueConstraint("ticker_id", "price_date", name="uq_daily_price_ticker_date"),
        Index("ix_daily_price_ticker_date", "ticker_id", "price_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    ticker: Mapped[Ticker] = relationship(back_populates="prices")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"DailyPrice(ticker_id={self.ticker_id!r}, date={self.price_date!r})"
