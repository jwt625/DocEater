"""Database models for DocEater."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LogLevel(str, Enum):
    """Log level for processing logs."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ImageType(str, Enum):
    """Type of extracted image."""
    PICTURE = "picture"
    TABLE = "table"
    FORMULA = "formula"
    CHART = "chart"
    DIAGRAM = "diagram"
    PAGE = "page"


class Document(Base):
    """Document table for storing file information and content."""

    __tablename__ = "documents"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # File information
    file_path: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
        index=True
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    # Content
    markdown_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    images: Mapped[list[DocumentImage]] = relationship(
        "DocumentImage",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class DocumentImage(Base):
    """Document images table for storing extracted image information."""

    __tablename__ = "document_images"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

    # Foreign key to document
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # File information
    image_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Relative path from images root directory"
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original extracted filename"
    )
    image_type: Mapped[ImageType] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Type of image: picture, table, formula, etc."
    )
    image_index: Mapped[int] = mapped_column(
        nullable=False,
        comment="Order/index within the document"
    )

    # Image properties
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Image file size in bytes"
    )
    width: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Image width in pixels"
    )
    height: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Image height in pixels"
    )
    format: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Image format: PNG, JPEG, WEBP, etc."
    )

    # Processing metadata
    extraction_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="docling",
        comment="Method used for extraction"
    )
    quality_score: Mapped[float | None] = mapped_column(
        nullable=True,
        comment="Optional quality assessment score"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        index=True
    )

    # Relationships
    document: Mapped[Document] = relationship(
        "Document",
        back_populates="images"
    )

    def __repr__(self) -> str:
        return f"<DocumentImage(id={self.id}, document_id={self.document_id}, type='{self.image_type}', filename='{self.filename}')>"


class DocumentMetadata(Base):
    """Flexible metadata storage for documents."""

    __tablename__ = "document_metadata"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign key to document
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )

    # Metadata key-value
    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now()
    )

    def __repr__(self) -> str:
        return f"<DocumentMetadata(document_id={self.document_id}, key='{self.key}')>"


class ProcessingLog(Base):
    """Processing logs and errors."""

    __tablename__ = "processing_logs"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Foreign key to document (optional for system-wide logs)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True
    )

    # Log details
    level: Mapped[LogLevel] = mapped_column(
        String(10),
        nullable=False,
        index=True
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        index=True
    )

    def __repr__(self) -> str:
        return f"<ProcessingLog(level='{self.level}', document_id={self.document_id})>"
