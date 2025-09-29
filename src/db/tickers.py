from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List
from contextlib import contextmanager


class TickerRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @contextmanager
    def _session(self):
        """
        Sesión transaccional.
        Todo lo que ejecutes dentro es atómico: si falla algo -> rollback.
        """
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _migrate(self) -> None:
        with self._session() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tickers (
                    symbol TEXT PRIMARY KEY
                );
            """)

    # ---------------- Operaciones públicas ----------------
    def list(self, limit: int = 100) -> List[str]:
        with self._session() as conn:
            cur = conn.execute(
                "SELECT symbol FROM tickers ORDER BY symbol ASC LIMIT ?;",
                (limit,),
            )
            rows = [r[0] for r in cur.fetchall()]
            print(f"Rows: {rows}")
        return rows  # fuera del with, ya leímos los datos

    def add_many(self, symbols: Iterable[str]) -> int:
        symbols = list(symbols)
        if not symbols:
            return 0
        with self._session() as conn:
            cur = conn.executemany(
                "INSERT OR IGNORE INTO tickers(symbol) VALUES (?);",
                [(s,) for s in symbols],
            )
            inserted = max(cur.rowcount or 0, 0)
        return inserted

    def remove(self, symbol: str) -> int:
        with self._session() as conn:
            cur = conn.execute("DELETE FROM tickers WHERE symbol = ?;", (symbol,))
            deleted = max(cur.rowcount or 0, 0)
        return deleted

    def replace_all(self, symbols: Iterable[str]) -> None:
        symbols = list(symbols)
        with self._session() as conn:
            conn.execute("DELETE FROM tickers;")
            if symbols:
                conn.executemany(
                    "INSERT OR IGNORE INTO tickers(symbol) VALUES (?);",
                    [(s,) for s in symbols],
                )

    def is_empty(self) -> bool:
        with self._session() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM tickers;")
            (count,) = cur.fetchone()
        return count == 0
