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
    DocumentImage,
    DocumentMetadata,
    DocumentStatus,
    ImageType,
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
            db_url = self.settings.database_url

            # Handle PostgreSQL URL conversion
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
            # For SQLite URLs, keep them as-is (sqlite+aiosqlite:// or sqlite://)
            # For other databases, assume they're already properly formatted

            # Configure engine parameters based on database type
            engine_kwargs = {
                "echo": self.settings.log_level == "DEBUG",
                "pool_pre_ping": True,
            }

            # Only add PostgreSQL-specific pool settings for PostgreSQL
            if "postgresql" in db_url:
                engine_kwargs.update(
                    {
                        "pool_size": 10,
                        "max_overflow": 20,
                    }
                )

            self._engine = create_async_engine(db_url, **engine_kwargs)
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
                    processed_at=func.now()
                    if status == DocumentStatus.COMPLETED
                    else None,
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
                update(Document).where(Document.id == document_id).values(status=status)
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

    async def get_document_metadata(self, document_id: uuid.UUID) -> dict[str, str]:
        """Get all metadata for a document."""
        async with self.get_session() as session:
            result = await session.execute(
                select(DocumentMetadata).where(
                    DocumentMetadata.document_id == document_id
                )
            )
            metadata_entries = result.scalars().all()

            return {entry.key: entry.value for entry in metadata_entries}

    # Image operations
    async def create_document_image(
        self,
        document_id: uuid.UUID,
        image_path: str,
        filename: str,
        image_type: ImageType,
        image_index: int,
        file_size: int,
        width: int | None = None,
        height: int | None = None,
        format: str | None = None,
        extraction_method: str | None = "docling",
        quality_score: float | None = None,
    ) -> DocumentImage:
        """Create a new document image record."""
        image = DocumentImage(
            document_id=document_id,
            image_path=image_path,
            filename=filename,
            image_type=image_type,
            image_index=image_index,
            file_size=file_size,
            width=width,
            height=height,
            format=format,
            extraction_method=extraction_method,
            quality_score=quality_score,
        )

        async with self.get_session() as session:
            session.add(image)
            await session.flush()  # Get the ID
            await session.refresh(image)

        logger.debug(f"Created image record: {image.id} for document {document_id}")
        return image

    async def get_document_images(
        self, document_id: uuid.UUID
    ) -> Sequence[DocumentImage]:
        """Get all images for a document."""
        async with self.get_session() as session:
            result = await session.execute(
                select(DocumentImage)
                .where(DocumentImage.document_id == document_id)
                .order_by(DocumentImage.image_index)
            )
            return result.scalars().all()

    async def get_document_image_by_id(
        self, image_id: uuid.UUID
    ) -> DocumentImage | None:
        """Get a specific document image by ID."""
        async with self.get_session() as session:
            result = await session.execute(
                select(DocumentImage).where(DocumentImage.id == image_id)
            )
            return result.scalar_one_or_none()

    async def delete_document_images(self, document_id: uuid.UUID) -> int:
        """Delete all images for a document. Returns count of deleted images."""
        async with self.get_session() as session:
            result = await session.execute(
                select(DocumentImage).where(DocumentImage.document_id == document_id)
            )
            images = result.scalars().all()
            count = len(images)

            for image in images:
                await session.delete(image)

        logger.debug(f"Deleted {count} images for document {document_id}")
        return count

    async def get_images_by_type(
        self, image_type: ImageType, limit: int = 100, offset: int = 0
    ) -> Sequence[DocumentImage]:
        """Get images by type across all documents."""
        async with self.get_session() as session:
            query = (
                select(DocumentImage)
                .where(DocumentImage.image_type == image_type)
                .order_by(DocumentImage.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(query)
            return result.scalars().all()

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

    async def get_processing_logs(
        self,
        document_id: uuid.UUID | None = None,
        level: LogLevel | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ProcessingLog]:
        """Get processing logs with optional filtering."""
        async with self.get_session() as session:
            query = select(ProcessingLog).order_by(ProcessingLog.created_at.desc())

            if document_id:
                query = query.where(ProcessingLog.document_id == document_id)

            if level:
                query = query.where(ProcessingLog.level == level)

            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            return result.scalars().all()


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
