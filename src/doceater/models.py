"""Database models for DocEater."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
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
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )

    # File information
    file_path: Mapped[str] = mapped_column(
        Text, unique=True, nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Content
    markdown_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        String(20), nullable=False, default=DocumentStatus.PENDING, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    images: Mapped[list[DocumentImage]] = relationship(
        "DocumentImage", back_populates="document", cascade="all, delete-orphan"
    )
    text_embeddings: Mapped[list["TextEmbedding"]] = relationship(
        "TextEmbedding", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class DocumentImage(Base):
    """Document images table for storing extracted image information."""

    __tablename__ = "document_images"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )

    # Foreign key to document
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File information
    image_path: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Relative path from images root directory"
    )
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Original extracted filename"
    )
    image_type: Mapped[ImageType] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Type of image: picture, table, formula, etc.",
    )
    image_index: Mapped[int] = mapped_column(
        nullable=False, comment="Order/index within the document"
    )

    # Image properties
    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Image file size in bytes"
    )
    width: Mapped[int | None] = mapped_column(
        nullable=True, comment="Image width in pixels"
    )
    height: Mapped[int | None] = mapped_column(
        nullable=True, comment="Image height in pixels"
    )
    format: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="Image format: PNG, JPEG, WEBP, etc."
    )

    # Processing metadata
    extraction_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="docling",
        comment="Method used for extraction",
    )
    quality_score: Mapped[float | None] = mapped_column(
        nullable=True, comment="Optional quality assessment score"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), index=True
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="images")
    image_embeddings: Mapped[list["ImageEmbedding"]] = relationship(
        "ImageEmbedding", back_populates="document_image", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DocumentImage(id={self.id}, document_id={self.document_id}, type='{self.image_type}', filename='{self.filename}')>"


class DocumentMetadata(Base):
    """Flexible metadata storage for documents."""

    __tablename__ = "document_metadata"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key to document
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Metadata key-value
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )

    def __repr__(self) -> str:
        return f"<DocumentMetadata(document_id={self.document_id}, key='{self.key}')>"


class ProcessingLog(Base):
    """Processing logs and errors."""

    __tablename__ = "processing_logs"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key to document (optional for system-wide logs)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Log details
    level: Mapped[LogLevel] = mapped_column(String(10), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<ProcessingLog(level='{self.level}', document_id={self.document_id})>"


class TextEmbedding(Base):
    """Text embeddings table for storing text chunk embeddings."""

    __tablename__ = "text_embeddings"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )

    # Foreign key to document
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Text content and embedding
    chunk_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Text content of the chunk"
    )
    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(item_type=Text), nullable=False,
        comment="1024-dimensional embedding vector from Jina CLIP v2"
    )

    # Position information
    page_number: Mapped[int | None] = mapped_column(
        nullable=True, comment="Page number where this chunk appears"
    )
    bbox_coordinates: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, comment="Bounding box coordinates {x, y, width, height}"
    )
    chunk_index: Mapped[int] = mapped_column(
        nullable=False, comment="Order of this chunk within the document"
    )
    token_count: Mapped[int | None] = mapped_column(
        nullable=True, comment="Number of tokens in the chunk"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), index=True
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="text_embeddings")

    def __repr__(self) -> str:
        return f"<TextEmbedding(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"


class ImageEmbedding(Base):
    """Image embeddings table for storing image embeddings."""

    __tablename__ = "image_embeddings"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )

    # Foreign key to document image
    document_image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_images.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Embedding and metadata
    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(item_type=Text), nullable=False,
        comment="1024-dimensional embedding vector from Jina CLIP v2"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Optional description or caption for the image"
    )
    ocr_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="OCR extracted text for better retrieval"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), index=True
    )

    # Relationships
    document_image: Mapped[DocumentImage] = relationship("DocumentImage", back_populates="image_embeddings")

    def __repr__(self) -> str:
        return f"<ImageEmbedding(id={self.id}, document_image_id={self.document_image_id})>"
