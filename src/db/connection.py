"""
Database connection module using SQLAlchemy asyncio for PostgreSQL.

This module provides async database engine and session management
for the stock widget application.
"""

import logging
import inspect
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine, 
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker
)
from utils.config import Config

logger = logging.getLogger(__name__)

class DatabaseConfigurationError(Exception):
    """Raised when database configuration is invalid."""

class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""


class DatabaseConnection:
    """
    Database connection manager using SQLAlchemy async for PostgreSQL.

    Design notes (singleton + responsibilities):
    - This class manages a single AsyncEngine instance via `_engine` (singleton pattern).
      Use `get_async_engine()` to obtain it; it will be created on first use.
    - `create_async_engine()` validates config and creates the engine once (early return
      if already created).
    - `create_async_session_factory()` builds a session factory bound to the engine.
    - `close_async_engine()` disposes the engine and resets internal state; call on shutdown.

    Keep I/O concerns here (adapters layer) and leave business logic outside.
    """
    
    # Single source of truth for engine (simpler for junior developers)
    _engine: AsyncEngine | None = None
    _async_session_factory: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    async def create_async_engine(cls) -> None:
        """
        Create the SQLAlchemy async engine with asyncpg driver.
        
        Raises:
            DatabaseConfigurationError: If database configuration is invalid
            DatabaseConnectionError: If engine creation fails
        """
        # Singleton guard: do not recreate the engine if it already exists
        if cls._engine is not None:
            return
        db_config = Config.load()
        
        # Validate required configuration
        if not db_config.DB_PASSWORD:
            raise DatabaseConfigurationError("DB_PASSWORD must be set in environment variables")
        
        # Build async database URL
        database_url = (
            f"postgresql+asyncpg://{db_config.DB_USER}:{db_config.DB_PASSWORD}"
            f"@{db_config.DB_HOST}:{db_config.DB_PORT}/{db_config.DB_NAME}"
        )
        
        try:
            # Create async engine with connection pooling
            engine = create_async_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False,  # Set to True for SQL debugging
                future=True,
            )
            cls._engine = engine
            logger.info(
                "Async database engine created successfully",
                extra={
                    "event": "async_database_engine_created",
                    "host": db_config.DB_HOST,
                    "port": db_config.DB_PORT,
                    "database": db_config.DB_NAME,
                }
            )
        
        except Exception as error:
            logger.error(
                "Failed to create async database engine",
                extra={
                    "event": "async_database_engine_creation_failed",
                    "error": str(error),
                    "host": db_config.DB_HOST,
                    "port": db_config.DB_PORT,
                }
            )
            raise DatabaseConnectionError(f"Async database engine creation failed: {error}") from error

    @classmethod
    async def get_async_engine(cls) -> AsyncEngine:
        """
        Get or create the SQLAlchemy async engine.
        
        Returns:
            AsyncEngine: Configured async engine instance
            
        Raises:
            DatabaseConnectionError: If engine creation fails
        """
        if cls._engine is None:
            await cls.create_async_engine()
        return cls._engine  # type: ignore[return-value]

    @classmethod
    async def create_async_session_factory(cls) -> None:
        """
        Create the async session factory using the async engine.
        """
        # Support both real async method and patched non-awaitable mocks in tests
        maybe_engine = cls.get_async_engine()
        engine = await maybe_engine if inspect.isawaitable(maybe_engine) else maybe_engine
        cls._async_session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession
        )
        logger.info("Async session factory created successfully")

    @classmethod
    async def get_async_session_factory(cls) -> async_sessionmaker[AsyncSession]:
        """
        Get or create the async session factory.
        
        Returns:
            async_sessionmaker[AsyncSession]: Configured async session factory
        """
        if cls._async_session_factory is None:
            await cls.create_async_session_factory()
        return cls._async_session_factory

    @classmethod
    async def close_async_engine(cls) -> None:
        """
        Close the async database engine and dispose of connection pool.
        
        Should be called when shutting down the application.
        """
        if cls._engine is not None:
            await cls._engine.dispose()
            cls._engine = None
            cls._async_session_factory = None
            logger.info("Async database engine closed and disposed")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Behavior:
    - Yields a session for use within an `async with` block.
    - If the block raises, performs `rollback()` and logs the error.
    - Always attempts `commit()` after the block; if commit fails, that error is propagated.
    - Closes the session exactly once in a `finally` block.
    
    Yields:
        AsyncSession: Async database session for use in async context
        
    Example:
        async with get_db_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
    """
    # Support both real async method and patched non-awaitable mocks in tests
    maybe_factory = DatabaseConnection.get_async_session_factory()
    session_factory = (
        await maybe_factory if inspect.isawaitable(maybe_factory) else maybe_factory
    )
    session = session_factory()
    original_exception: Exception | None = None
    try:
        try:
            yield session
        except Exception as error:
            original_exception = error
            await session.rollback()
            logger.exception("Database operation error")
        # Attempt commit regardless; if it fails, propagate commit error
        await session.commit()
        # If there was an original error but commit succeeded, propagate it after commit
        if original_exception is not None:
            raise original_exception
    finally:
        # Close session exactly once in all paths
        try:
            await session.close()
        except Exception:
            # Swallow close errors to not mask prior exceptions
            pass
