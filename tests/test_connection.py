"""
Tests for database connection module.

This module tests the DatabaseConnection class and related functionality
for PostgreSQL connection management using SQLAlchemy.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession

from db.connection import DatabaseConnection, get_db_session


class TestDatabaseConnection:
    """Test suite for the DatabaseConnection class."""

    @pytest.fixture(autouse=True)
    def setup_env(self, tmp_path) -> None:
        """Create a temporary .env file for testing."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "DB_HOST=testhost\n"
            "DB_PORT=9999\n"
            "DB_NAME=testdb\n"
            "DB_USER=testuser\n"
            "DB_PASSWORD=testpass\n"
            "MARKET_TIMEZONE=America/New_York\n"
            "MAX_TICKERS=100"
        )
        os.environ["DOTENV_PATH"] = str(env_file)
        yield
        # Cleanup
        if "DOTENV_PATH" in os.environ:
            del os.environ["DOTENV_PATH"]

    @pytest.fixture(autouse=True)
    def reset_connection(self) -> None:
        """Reset database connection state between tests."""
        DatabaseConnection._engine = None
        DatabaseConnection._async_session_factory = None
        yield

    async def test_get_async_engine_success(self):
        with patch("db.connection.create_async_engine") as mock_create_async_engine:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create_async_engine.return_value = mock_engine

            await DatabaseConnection.create_async_engine()
            engine = DatabaseConnection._engine

            assert engine is mock_engine
            mock_create_async_engine.assert_called_once()

            args, kwargs = mock_create_async_engine.call_args
            url = str(args[0])
            assert url.startswith(
                "postgresql+asyncpg://testuser:testpass@testhost:9999/testdb"
            )

    async def test_get_async_engine_singleton_pattern(self):
        """Test that async engine is created only once."""
        with patch("db.connection.create_async_engine") as mock_create_async_engine:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create_async_engine.return_value = mock_engine

            await DatabaseConnection.create_async_engine()
            engine1 = DatabaseConnection._engine
            await DatabaseConnection.create_async_engine()
            engine2 = DatabaseConnection._engine

            assert engine1 is engine2
            assert mock_create_async_engine.call_count == 1

    async def test_get_async_session_factory_success(self):
        """Test successful async session factory creation."""
        with patch(
            "db.connection.DatabaseConnection.get_async_engine"
        ) as mock_get_engine:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_get_engine.return_value = mock_engine

            await DatabaseConnection.create_async_session_factory()
            session_factory = await DatabaseConnection.get_async_session_factory()

            assert session_factory is not None
            assert isinstance(session_factory, async_sessionmaker)

    async def test_get_db_session_success(self):
        """Test successful database session context manager."""
        with patch(
            "db.connection.DatabaseConnection.get_async_session_factory"
        ) as mock_get_factory:
            mock_session_factory = MagicMock()
            mock_get_factory.return_value = mock_session_factory
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_factory.return_value = mock_session

            async with get_db_session() as session:
                assert session is mock_session

            # Verify session operations
            mock_session.commit.assert_awaited_once()
            mock_session.close.assert_awaited_once()

    async def test_get_db_session_rollback_on_error(self):
        """Test database session rollback on error."""
        with patch(
            "db.connection.DatabaseConnection.get_async_session_factory"
        ) as mock_get_factory:
            mock_session_factory = MagicMock()
            mock_get_factory.return_value = mock_session_factory
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_factory.return_value = mock_session
            mock_session.commit.side_effect = Exception("Commit failed")

            with pytest.raises(Exception, match="Commit failed"):
                async with get_db_session():
                    raise Exception("Test error")

            # Verify rollback was called
            mock_session.rollback.assert_awaited_once()
            mock_session.close.assert_awaited_once()
