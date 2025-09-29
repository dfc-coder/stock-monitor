# db/tickers.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple, Any
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tickers (
                    symbol TEXT PRIMARY KEY,
                    follow INTEGER NOT NULL DEFAULT 0
                );
            """
            )

    # -------- Lecturas --------
    def list(self, limit: int = 100) -> List[str]:
        # Solo los seguidos
        with self._session() as conn:
            cur = conn.execute(
                "SELECT symbol FROM tickers WHERE follow > 0 ORDER BY symbol ASC LIMIT ?;",
                (limit,),
            )
            return [r[0] for r in cur.fetchall()]

    def list_all(self) -> List[Tuple[str, int]]:
        # Todos con su follow (para Settings)
        with self._session() as conn:
            cur = conn.execute(
                "SELECT symbol, follow FROM tickers ORDER BY symbol ASC;"
            )
            return [(r[0], int(r[1])) for r in cur.fetchall()]

    # -------- Escrituras eficientes --------
    def upsert_many(self, symbols: Iterable[str]) -> int:
        symbols = list(symbols)
        if not symbols:
            return 0
        with self._session() as conn:
            cur = conn.executemany(
                "INSERT OR IGNORE INTO tickers(symbol) VALUES (?);",
                [(s,) for s in symbols],
            )
            return max(cur.rowcount or 0, 0)

    def set_follow_many(self, symbols: Iterable[str], follow: int) -> int:
        syms = [s for s in symbols]
        if not syms:
            return 0
        placeholders = ",".join(["?"] * len(syms))
        params: Sequence[Any] = (follow, *syms)
        with self._session() as conn:
            cur = conn.execute(
                f"UPDATE tickers SET follow = ? WHERE symbol IN ({placeholders});",
                params,
            )
            return max(cur.rowcount or 0, 0)

    def remove_many(self, symbols: Iterable[str]) -> int:
        syms = [s for s in symbols]
        if not syms:
            return 0
        placeholders = ",".join(["?"] * len(syms))
        with self._session() as conn:
            cur = conn.execute(
                f"DELETE FROM tickers WHERE symbol IN ({placeholders});",
                syms,
            )
            return max(cur.rowcount or 0, 0)

    def is_empty(self) -> bool:
        with self._session() as conn:
            (count,) = conn.execute("SELECT COUNT(*) FROM tickers;").fetchone()
            return count == 0
