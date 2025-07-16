"""Tests for database models."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from doceater.models import Document, DocumentMetadata, DocumentStatus, LogLevel, ProcessingLog


class TestDocumentStatus:
    """Test DocumentStatus enum."""

    def test_status_values(self):
        """Test that status enum has correct values."""
        assert DocumentStatus.PENDING == "pending"
        assert DocumentStatus.PROCESSING == "processing"
        assert DocumentStatus.COMPLETED == "completed"
        assert DocumentStatus.FAILED == "failed"

    def test_status_iteration(self):
        """Test that we can iterate over all statuses."""
        statuses = list(DocumentStatus)
        assert len(statuses) == 4
        assert DocumentStatus.PENDING in statuses
        assert DocumentStatus.PROCESSING in statuses
        assert DocumentStatus.COMPLETED in statuses
        assert DocumentStatus.FAILED in statuses


class TestLogLevel:
    """Test LogLevel enum."""

    def test_log_level_values(self):
        """Test that log level enum has correct values."""
        assert LogLevel.INFO == "info"
        assert LogLevel.WARNING == "warning"
        assert LogLevel.ERROR == "error"

    def test_log_level_iteration(self):
        """Test that we can iterate over all log levels."""
        levels = list(LogLevel)
        assert len(levels) == 3
        assert LogLevel.INFO in levels
        assert LogLevel.WARNING in levels
        assert LogLevel.ERROR in levels


class TestDocument:
    """Test Document model."""

    def test_document_table_structure(self):
        """Test Document table structure and column definitions."""
        # Test table name
        assert Document.__tablename__ == "documents"

        # Test that required columns exist
        columns = Document.__table__.columns
        assert "id" in columns
        assert "file_path" in columns
        assert "filename" in columns
        assert "content_hash" in columns
        assert "file_size" in columns
        assert "mime_type" in columns
        assert "markdown_content" in columns
        assert "status" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_document_creation_with_values(self):
        """Test creating a Document instance with explicit values."""
        doc_id = uuid.uuid4()
        now = datetime.now()

        doc = Document()
        doc.id = doc_id
        doc.file_path = "/test/path/document.pdf"
        doc.filename = "document.pdf"
        doc.content_hash = "abc123"
        doc.file_size = 1024
        doc.mime_type = "application/pdf"
        doc.markdown_content = "# Test Document"
        doc.status = DocumentStatus.COMPLETED
        doc.created_at = now
        doc.updated_at = now

        assert doc.id == doc_id
        assert doc.file_path == "/test/path/document.pdf"
        assert doc.filename == "document.pdf"
        assert doc.content_hash == "abc123"
        assert doc.file_size == 1024
        assert doc.mime_type == "application/pdf"
        assert doc.markdown_content == "# Test Document"
        assert doc.status == DocumentStatus.COMPLETED
        assert doc.created_at == now
        assert doc.updated_at == now

    def test_document_repr(self):
        """Test Document string representation."""
        doc = Document()
        doc.filename = "document.pdf"

        repr_str = repr(doc)
        assert "Document" in repr_str
        assert "document.pdf" in repr_str


class TestDocumentMetadata:
    """Test DocumentMetadata model."""

    def test_metadata_table_structure(self):
        """Test DocumentMetadata table structure."""
        assert DocumentMetadata.__tablename__ == "document_metadata"

        columns = DocumentMetadata.__table__.columns
        assert "id" in columns
        assert "document_id" in columns
        assert "key" in columns
        assert "value" in columns
        assert "created_at" in columns

    def test_metadata_creation_with_values(self):
        """Test creating a DocumentMetadata instance with explicit values."""
        doc_id = uuid.uuid4()
        metadata_id = uuid.uuid4()
        now = datetime.now()

        metadata = DocumentMetadata()
        metadata.id = metadata_id
        metadata.document_id = doc_id
        metadata.key = "author"
        metadata.value = "John Doe"
        metadata.created_at = now

        assert metadata.id == metadata_id
        assert metadata.document_id == doc_id
        assert metadata.key == "author"
        assert metadata.value == "John Doe"
        assert metadata.created_at == now

    def test_metadata_null_value(self):
        """Test DocumentMetadata with null value."""
        doc_id = uuid.uuid4()

        metadata = DocumentMetadata()
        metadata.document_id = doc_id
        metadata.key = "description"
        metadata.value = None

        assert metadata.key == "description"
        assert metadata.value is None

    def test_metadata_repr(self):
        """Test DocumentMetadata string representation."""
        doc_id = uuid.uuid4()

        metadata = DocumentMetadata()
        metadata.document_id = doc_id
        metadata.key = "author"

        repr_str = repr(metadata)
        assert "DocumentMetadata" in repr_str
        assert str(doc_id) in repr_str
        assert "author" in repr_str


class TestProcessingLog:
    """Test ProcessingLog model."""

    def test_log_table_structure(self):
        """Test ProcessingLog table structure."""
        assert ProcessingLog.__tablename__ == "processing_logs"

        columns = ProcessingLog.__table__.columns
        assert "id" in columns
        assert "document_id" in columns
        assert "level" in columns
        assert "message" in columns
        assert "details" in columns
        assert "created_at" in columns

    def test_log_creation_with_values(self):
        """Test creating a ProcessingLog instance with explicit values."""
        doc_id = uuid.uuid4()
        log_id = uuid.uuid4()
        now = datetime.now()

        log = ProcessingLog()
        log.id = log_id
        log.document_id = doc_id
        log.level = LogLevel.INFO
        log.message = "Processing started"
        log.details = {"file_size": 1024}
        log.created_at = now

        assert log.id == log_id
        assert log.document_id == doc_id
        assert log.level == LogLevel.INFO
        assert log.message == "Processing started"
        assert log.details == {"file_size": 1024}
        assert log.created_at == now

    def test_log_system_message(self):
        """Test ProcessingLog for system messages (no document_id)."""
        log = ProcessingLog()
        log.document_id = None
        log.level = LogLevel.WARNING
        log.message = "System warning"
        log.details = {"component": "watcher"}

        assert log.document_id is None
        assert log.level == LogLevel.WARNING
        assert log.message == "System warning"
        assert log.details == {"component": "watcher"}

    def test_log_repr(self):
        """Test ProcessingLog string representation."""
        doc_id = uuid.uuid4()

        log = ProcessingLog()
        log.document_id = doc_id
        log.level = LogLevel.INFO

        repr_str = repr(log)
        assert "ProcessingLog" in repr_str
        assert str(doc_id) in repr_str
        assert "LogLevel.INFO" in repr_str
