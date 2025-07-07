"""Database connection and operations for DocEater."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import Settings, get_settings
from .models import (
    Base,
    Document,
    DocumentMetadata,
    DocumentStatus,
    LogLevel,
    ProcessingLog,
)


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Get or create the database engine."""
        if self._engine is None:
            # Convert postgresql:// to postgresql+asyncpg://
            db_url = self.settings.database_url
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif not db_url.startswith("postgresql+asyncpg://"):
                db_url = f"postgresql+asyncpg://{db_url}"

            self._engine = create_async_engine(
                db_url,
                echo=self.settings.log_level == "DEBUG",
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create the session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._session_factory

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        """Get a database session."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_tables(self) -> None:
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

    async def drop_tables(self) -> None:
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully")

    async def close(self) -> None:
        """Close the database connection."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
        logger.info("Database connection closed")

    # Document operations
    async def create_document(
        self,
        file_path: str,
        filename: str,
        content_hash: str,
        file_size: int,
        mime_type: str | None = None,
    ) -> Document:
        """Create a new document record."""
        document = Document(
            file_path=file_path,
            filename=filename,
            content_hash=content_hash,
            file_size=file_size,
            mime_type=mime_type,
        )

        async with self.get_session() as session:
            session.add(document)
            await session.flush()
            await session.refresh(document)

        logger.info(f"Created document record: {document.id} ({filename})")
        return document

    async def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Get a document by ID."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Document).where(Document.id == document_id)
            )
            return result.scalar_one_or_none()

    async def get_document_by_path(self, file_path: str) -> Document | None:
        """Get a document by file path."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Document).where(Document.file_path == file_path)
            )
            return result.scalar_one_or_none()

    async def get_document_by_hash(self, content_hash: str) -> Document | None:
        """Get a document by content hash."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Document).where(Document.content_hash == content_hash)
            )
            return result.scalar_one_or_none()

    async def update_document_content(
        self,
        document_id: uuid.UUID,
        markdown_content: str,
        status: DocumentStatus = DocumentStatus.COMPLETED,
    ) -> None:
        """Update document content and status."""
        async with self.get_session() as session:
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    markdown_content=markdown_content,
                    status=status,
                    processed_at=func.now() if status == DocumentStatus.COMPLETED else None,
                )
            )

        logger.info(f"Updated document content: {document_id}")

    async def update_document_status(
        self,
        document_id: uuid.UUID,
        status: DocumentStatus,
    ) -> None:
        """Update document status."""
        async with self.get_session() as session:
            await session.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(status=status)
            )

        logger.debug(f"Updated document status: {document_id} -> {status}")

    async def list_documents(
        self,
        status: DocumentStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Document]:
        """List documents with optional filtering."""
        async with self.get_session() as session:
            query = select(Document).order_by(Document.created_at.desc())

            if status:
                query = query.where(Document.status == status)

            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            return result.scalars().all()

    # Metadata operations
    async def add_document_metadata(
        self,
        document_id: uuid.UUID,
        metadata: dict[str, str],
    ) -> None:
        """Add metadata to a document."""
        async with self.get_session() as session:
            for key, value in metadata.items():
                metadata_obj = DocumentMetadata(
                    document_id=document_id,
                    key=key,
                    value=value,
                )
                session.add(metadata_obj)

        logger.debug(f"Added metadata to document: {document_id}")

    # Logging operations
    async def log_processing(
        self,
        level: LogLevel,
        message: str,
        document_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a processing event."""
        log_entry = ProcessingLog(
            document_id=document_id,
            level=level,
            message=message,
            details=details,
        )

        async with self.get_session() as session:
            session.add(log_entry)

        # Also log to application logger
        log_func = getattr(logger, level.value.lower())
        log_func(f"[{document_id or 'SYSTEM'}] {message}")


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
