"""Tests for database operations."""

from __future__ import annotations

import uuid

import pytest

from doceater.database import DatabaseManager
from doceater.models import (
    Document,
    DocumentStatus,
    LogLevel,
)


class TestDatabaseManager:
    """Test DatabaseManager operations."""

    @pytest.mark.asyncio
    async def test_create_and_drop_tables(self, test_db_manager: DatabaseManager):
        """Test creating and dropping database tables."""
        # Tables should already be created by the fixture
        # Test that we can drop and recreate them
        await test_db_manager.drop_tables()
        await test_db_manager.create_tables()

        # Verify tables exist by trying to query them
        from sqlalchemy import text

        async with test_db_manager.get_session() as session:
            # This should not raise an error if tables exist
            result = await session.execute(text("SELECT COUNT(*) FROM documents"))
            assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_create_document(self, test_db_manager: DatabaseManager):
        """Test creating a document."""
        doc = await test_db_manager.create_document(
            file_path="/test/path/document.pdf",
            filename="document.pdf",
            content_hash="abc123",
            file_size=1024,
            mime_type="application/pdf",
        )

        assert isinstance(doc, Document)
        assert isinstance(doc.id, uuid.UUID)

        # Verify document properties
        assert doc.file_path == "/test/path/document.pdf"
        assert doc.filename == "document.pdf"
        assert doc.content_hash == "abc123"
        assert doc.file_size == 1024
        assert doc.mime_type == "application/pdf"
        assert doc.status == DocumentStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_document_by_path(self, test_db_manager: DatabaseManager):
        """Test getting document by file path."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/unique/path.pdf",
            filename="path.pdf",
            content_hash="unique123",
            file_size=2048,
        )

        # Get by path
        doc = await test_db_manager.get_document_by_path("/test/unique/path.pdf")
        assert doc is not None
        assert doc.id == created_doc.id
        assert doc.filename == "path.pdf"

        # Test non-existent path
        doc = await test_db_manager.get_document_by_path("/non/existent/path.pdf")
        assert doc is None

    @pytest.mark.asyncio
    async def test_get_document_by_hash(self, test_db_manager: DatabaseManager):
        """Test getting document by content hash."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/hash/test.pdf",
            filename="test.pdf",
            content_hash="uniquehash123",
            file_size=1024,
        )

        # Get by hash
        doc = await test_db_manager.get_document_by_hash("uniquehash123")
        assert doc is not None
        assert doc.id == created_doc.id
        assert doc.content_hash == "uniquehash123"

        # Test non-existent hash
        doc = await test_db_manager.get_document_by_hash("nonexistenthash")
        assert doc is None

    @pytest.mark.asyncio
    async def test_update_document_content(self, test_db_manager: DatabaseManager):
        """Test updating document content and status."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/update/doc.pdf",
            filename="doc.pdf",
            content_hash="update123",
            file_size=1024,
        )

        # Update content
        markdown_content = "# Updated Document\n\nThis is updated content."
        await test_db_manager.update_document_content(
            created_doc.id,
            markdown_content,
            DocumentStatus.COMPLETED,
        )

        # Verify update
        doc = await test_db_manager.get_document_by_id(created_doc.id)
        assert doc is not None
        assert doc.markdown_content == markdown_content
        assert doc.status == DocumentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_update_document_status(self, test_db_manager: DatabaseManager):
        """Test updating document status."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/status/doc.pdf",
            filename="doc.pdf",
            content_hash="status123",
            file_size=1024,
        )

        # Update status to processing
        await test_db_manager.update_document_status(
            created_doc.id, DocumentStatus.PROCESSING
        )

        doc = await test_db_manager.get_document_by_id(created_doc.id)
        assert doc is not None
        assert doc.status == DocumentStatus.PROCESSING

        # Update status to failed
        await test_db_manager.update_document_status(
            created_doc.id, DocumentStatus.FAILED
        )

        doc = await test_db_manager.get_document_by_id(created_doc.id)
        assert doc is not None
        assert doc.status == DocumentStatus.FAILED

    @pytest.mark.asyncio
    async def test_list_documents(self, test_db_manager: DatabaseManager):
        """Test listing documents with filters."""
        # Create multiple documents with different statuses
        doc1 = await test_db_manager.create_document(
            file_path="/test/list/doc1.pdf",
            filename="doc1.pdf",
            content_hash="list1",
            file_size=1024,
        )

        doc2 = await test_db_manager.create_document(
            file_path="/test/list/doc2.pdf",
            filename="doc2.pdf",
            content_hash="list2",
            file_size=2048,
        )

        # Update one to completed
        await test_db_manager.update_document_status(doc2.id, DocumentStatus.COMPLETED)

        # List all documents
        all_docs = await test_db_manager.list_documents()
        assert len(all_docs) >= 2

        # List only pending documents
        pending_docs = await test_db_manager.list_documents(
            status=DocumentStatus.PENDING
        )
        pending_ids = [doc.id for doc in pending_docs]
        assert doc1.id in pending_ids
        assert doc2.id not in pending_ids

        # List only completed documents
        completed_docs = await test_db_manager.list_documents(
            status=DocumentStatus.COMPLETED
        )
        completed_ids = [doc.id for doc in completed_docs]
        assert doc2.id in completed_ids
        assert doc1.id not in completed_ids

        # Test limit
        limited_docs = await test_db_manager.list_documents(limit=1)
        assert len(limited_docs) == 1

    @pytest.mark.asyncio
    async def test_document_exists_after_creation(
        self, test_db_manager: DatabaseManager
    ):
        """Test that a document exists after creation and can be retrieved."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/exists/doc.pdf",
            filename="doc.pdf",
            content_hash="exists123",
            file_size=1024,
        )

        # Verify it exists by ID
        doc = await test_db_manager.get_document_by_id(created_doc.id)
        assert doc is not None
        assert doc.id == created_doc.id
        assert doc.filename == "doc.pdf"

        # Verify it exists by path
        doc_by_path = await test_db_manager.get_document_by_path("/test/exists/doc.pdf")
        assert doc_by_path is not None
        assert doc_by_path.id == created_doc.id

    @pytest.mark.asyncio
    async def test_add_document_metadata(self, test_db_manager: DatabaseManager):
        """Test adding document metadata."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/metadata/doc.pdf",
            filename="doc.pdf",
            content_hash="meta123",
            file_size=1024,
        )

        # Add metadata
        metadata = {
            "title": "Test Document",
            "author": "Test Author",
            "subject": "Testing",
            "keywords": "test, metadata",
        }
        await test_db_manager.add_document_metadata(created_doc.id, metadata)

        # Verify metadata was stored correctly
        stored_metadata = await test_db_manager.get_document_metadata(created_doc.id)
        assert stored_metadata == metadata

        # Add more metadata
        additional_metadata = {
            "title": "Updated Test Document",  # This should update existing
            "new_field": "New Value",  # This should add new
        }
        await test_db_manager.add_document_metadata(created_doc.id, additional_metadata)

        # Verify all metadata is present
        all_metadata = await test_db_manager.get_document_metadata(created_doc.id)
        expected_metadata = {
            "title": "Updated Test Document",  # Should be updated
            "author": "Test Author",  # Should remain
            "subject": "Testing",  # Should remain
            "keywords": "test, metadata",  # Should remain
            "new_field": "New Value",  # Should be added
        }
        assert all_metadata == expected_metadata

    @pytest.mark.asyncio
    async def test_get_document_metadata_empty(self, test_db_manager: DatabaseManager):
        """Test getting metadata for document with no metadata."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/empty_metadata/doc.pdf",
            filename="doc.pdf",
            content_hash="empty123",
            file_size=1024,
        )

        # Get metadata for document with no metadata
        metadata = await test_db_manager.get_document_metadata(created_doc.id)
        assert metadata == {}

    @pytest.mark.asyncio
    async def test_log_processing(self, test_db_manager: DatabaseManager):
        """Test logging processing events."""
        # Create a document
        created_doc = await test_db_manager.create_document(
            file_path="/test/log/doc.pdf",
            filename="doc.pdf",
            content_hash="log123",
            file_size=1024,
        )

        # Log processing events
        await test_db_manager.log_processing(
            LogLevel.INFO,
            "Processing started",
            created_doc.id,
            {"file_size": 1024},
        )

        await test_db_manager.log_processing(
            LogLevel.WARNING,
            "Minor issue encountered",
            created_doc.id,
        )

        await test_db_manager.log_processing(
            LogLevel.ERROR,
            "System error",
            None,  # System-level error
            {"error_code": 500},
        )

        # Verify logs were stored correctly
        all_logs = await test_db_manager.get_processing_logs()
        assert len(all_logs) == 3

        # Check document-specific logs
        doc_logs = await test_db_manager.get_processing_logs(document_id=created_doc.id)
        assert len(doc_logs) == 2

        # Check logs by level
        error_logs = await test_db_manager.get_processing_logs(level=LogLevel.ERROR)
        assert len(error_logs) == 1
        assert error_logs[0].message == "System error"
        assert error_logs[0].details == {"error_code": 500}

        # Check specific log content
        info_logs = await test_db_manager.get_processing_logs(
            document_id=created_doc.id, level=LogLevel.INFO
        )
        assert len(info_logs) == 1
        assert info_logs[0].message == "Processing started"
        assert info_logs[0].details == {"file_size": 1024}
