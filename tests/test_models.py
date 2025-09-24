"""
Unit tests for SQLAlchemy ORM models defined in src/data/models.py.

These tests validate:
- Table names and columns
- Relationships between Ticker and DailyPrice
- Unique constraints and indexes

They operate purely on SQLAlchemy metadata and mappers (no live DB required).
"""
from __future__ import annotations

from sqlalchemy.orm import class_mapper

from data.models import Base, Ticker, DailyPrice


def test_base_metadata_contains_tables():
    metadata = Base.metadata
    assert "tickers" in metadata.tables
    assert "daily_prices" in metadata.tables


def test_ticker_model_columns_and_indexes():
    ticker_table = Base.metadata.tables["tickers"]
    columns = {c.name for c in ticker_table.columns}
    assert {"id", "symbol", "name", "created_at"}.issubset(columns)

    # symbol must be unique and indexed
    symbol_col = ticker_table.c.symbol
    assert symbol_col.unique is True
    # Index may be implicit; verify presence of any index that includes symbol
    idx_columns_sets = [{c.name for c in idx.columns} for idx in ticker_table.indexes]
    assert any({"symbol"} <= cols for cols in idx_columns_sets)


def test_daily_price_model_columns_constraints_and_indexes():
    price_table = Base.metadata.tables["daily_prices"]
    columns = {c.name for c in price_table.columns}
    assert {"id", "ticker_id", "price_date", "open", "high", "low", "close", "volume", "created_at"}.issubset(columns)

    # Unique constraint on (ticker_id, price_date)
    unique_constraints = [uc for uc in price_table.constraints if getattr(uc, "columns", None)]
    has_unique = False
    for uc in unique_constraints:
        try:
            col_names = {c.name for c in uc.columns}
        except Exception:
            continue
        if col_names == {"ticker_id", "price_date"}:
            has_unique = True
            break
    assert has_unique, "Expected unique constraint on (ticker_id, price_date)"

    # Index on (ticker_id, price_date)
    idx_columns_sets = [{c.name for c in idx.columns} for idx in price_table.indexes]
    assert any({"ticker_id", "price_date"} <= cols for cols in idx_columns_sets)


def test_relationship_between_ticker_and_daily_price():
    ticker_mapper = class_mapper(Ticker)
    daily_price_mapper = class_mapper(DailyPrice)

    # Ticker.prices relationship
    rel = ticker_mapper.relationships.get("prices")
    assert rel is not None
    assert rel.mapper.class_ is DailyPrice
    assert rel.back_populates == "ticker"

    # DailyPrice.ticker relationship
    rel2 = daily_price_mapper.relationships.get("ticker")
    assert rel2 is not None
    assert rel2.mapper.class_ is Ticker
    assert rel2.back_populates == "prices"
