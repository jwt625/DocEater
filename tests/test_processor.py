"""Tests for document processor."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from doceater.models import DocumentStatus
from doceater.processor import DocumentProcessor


class TestDocumentProcessor:
    """Test DocumentProcessor class."""

    def test_processor_initialization(self, test_settings, test_db_manager):
        """Test DocumentProcessor initialization."""
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        assert processor.settings == test_settings
        assert processor.db_manager == test_db_manager
        assert processor._converter is None

    def test_processor_initialization_with_defaults(self):
        """Test DocumentProcessor initialization with default dependencies."""
        processor = DocumentProcessor()
        
        assert processor.settings is not None
        assert processor.db_manager is not None
        assert processor._converter is None

    @patch('doceater.processor.DocumentConverter')
    def test_converter_property(self, mock_converter_class, test_settings, test_db_manager):
        """Test converter property creates and caches converter."""
        mock_converter = MagicMock()
        mock_converter_class.return_value = mock_converter
        
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # First access should create converter
        converter1 = processor.converter
        assert converter1 == mock_converter
        mock_converter_class.assert_called_once()
        
        # Second access should return cached converter
        converter2 = processor.converter
        assert converter2 == mock_converter
        assert mock_converter_class.call_count == 1  # Still only called once

    @pytest.mark.asyncio
    async def test_calculate_file_hash(self, test_settings, test_db_manager, small_pdf_file):
        """Test file hash calculation with real PDF."""
        processor = DocumentProcessor(test_settings, test_db_manager)

        # Calculate hash for real PDF
        file_hash = await processor.calculate_file_hash(small_pdf_file)

        # Verify hash is a valid SHA-256 hex string
        assert len(file_hash) == 64  # SHA-256 produces 64-character hex string
        assert all(c in "0123456789abcdef" for c in file_hash)

        # Verify hash is consistent
        file_hash2 = await processor.calculate_file_hash(small_pdf_file)
        assert file_hash == file_hash2

    def test_get_mime_type(self, test_settings, test_db_manager):
        """Test MIME type detection."""
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Test PDF file
        pdf_path = Path("test.pdf")
        mime_type = processor.get_mime_type(pdf_path)
        assert mime_type == "application/pdf"
        
        # Test text file
        txt_path = Path("test.txt")
        mime_type = processor.get_mime_type(txt_path)
        assert mime_type == "text/plain"
        
        # Test unknown extension
        unknown_path = Path("test.unknown")
        mime_type = processor.get_mime_type(unknown_path)
        assert mime_type is None

    def test_is_supported_file(self, test_settings, test_db_manager, temp_dir):
        """Test file support detection."""
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Test supported file
        pdf_file = temp_dir / "test.pdf"
        pdf_file.touch()
        assert processor.is_supported_file(pdf_file) is True
        
        # Test unsupported extension
        doc_file = temp_dir / "test.doc"
        doc_file.touch()
        assert processor.is_supported_file(doc_file) is False
        
        # Test excluded pattern (hidden file)
        hidden_file = temp_dir / ".hidden.pdf"
        hidden_file.touch()
        assert processor.is_supported_file(hidden_file) is False
        
        # Test excluded pattern (temp file)
        temp_file = temp_dir / "test.tmp"
        temp_file.touch()
        assert processor.is_supported_file(temp_file) is False
        
        # Test file too large
        large_file = temp_dir / "large.pdf"
        large_file.touch()
        # Mock file size to be larger than limit
        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = test_settings.max_file_size_bytes + 1
            assert processor.is_supported_file(large_file) is False

    @pytest.mark.asyncio
    async def test_extract_metadata(self, test_settings, test_db_manager, small_pdf_file):
        """Test metadata extraction with real PDF."""
        processor = DocumentProcessor(test_settings, test_db_manager)

        # Extract metadata from real PDF file
        metadata = await processor.extract_metadata(small_pdf_file)

        # Verify metadata
        assert metadata["file_extension"] == ".pdf"
        assert "file_size_bytes" in metadata
        assert int(metadata["file_size_bytes"]) > 0  # Real PDF should have size
        assert "created_time" in metadata
        assert "modified_time" in metadata
        assert metadata.get("mime_type") == "application/pdf"

    @pytest.mark.asyncio
    async def test_extract_metadata_error_handling(self, test_settings, test_db_manager):
        """Test metadata extraction error handling."""
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Test with non-existent file
        non_existent = Path("/non/existent/file.pdf")
        metadata = await processor.extract_metadata(non_existent)
        
        # Should return empty dict on error
        assert metadata == {}

    @pytest.mark.asyncio
    @patch('doceater.processor.DocumentConverter')
    async def test_convert_to_markdown(self, mock_converter_class, test_settings, test_db_manager, create_test_file, temp_dir):
        """Test document conversion to Markdown."""
        # Setup mock converter
        mock_converter = MagicMock()
        mock_result = MagicMock()
        mock_document = MagicMock()
        mock_document.export_to_markdown.return_value = "# Test Document\n\nConverted content"
        mock_result.document = mock_document
        mock_converter.convert.return_value = mock_result
        mock_converter_class.return_value = mock_converter
        
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Create test file
        test_file = create_test_file(temp_dir, "test.pdf", b"PDF content")
        
        # Convert to markdown
        markdown = await processor.convert_to_markdown(test_file)
        
        # Verify conversion
        assert markdown == "# Test Document\n\nConverted content"
        mock_converter.convert.assert_called_once_with(str(test_file))
        mock_document.export_to_markdown.assert_called_once()

    @pytest.mark.asyncio
    @patch('doceater.processor.DocumentConverter')
    async def test_convert_to_markdown_error(self, mock_converter_class, test_settings, test_db_manager, create_test_file, temp_dir):
        """Test document conversion error handling."""
        # Setup mock converter to raise error
        mock_converter = MagicMock()
        mock_converter.convert.side_effect = Exception("Conversion failed")
        mock_converter_class.return_value = mock_converter
        
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Create test file
        test_file = create_test_file(temp_dir, "test.pdf", b"PDF content")
        
        # Conversion should raise exception
        with pytest.raises(Exception, match="Conversion failed"):
            await processor.convert_to_markdown(test_file)

    @pytest.mark.asyncio
    async def test_process_file_unsupported(self, test_settings, test_db_manager, create_test_file, temp_dir):
        """Test processing unsupported file."""
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Create unsupported file
        unsupported_file = create_test_file(temp_dir, "test.doc", "Content")
        
        # Process file
        result = await processor.process_file(unsupported_file)
        
        # Should return False for unsupported file
        assert result is False

    @pytest.mark.asyncio
    async def test_process_file_already_exists(self, test_settings, test_db_manager, create_test_file, temp_dir):
        """Test processing file that already exists in database."""
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Create test file
        content = b"Test PDF content"
        test_file = create_test_file(temp_dir, "test.pdf", content)
        
        # Mock database to return existing document
        with patch.object(test_db_manager, 'get_document_by_hash') as mock_get_by_hash:
            mock_doc = MagicMock()
            mock_get_by_hash.return_value = mock_doc
            
            # Process file
            result = await processor.process_file(test_file)
            
            # Should return True but not process again
            assert result is True
            mock_get_by_hash.assert_called_once()

    @pytest.mark.asyncio
    @patch('doceater.processor.DocumentConverter')
    async def test_process_file_success(self, mock_converter_class, test_settings, test_db_manager, create_test_file, temp_dir):
        """Test successful file processing."""
        # Setup mock converter
        mock_converter = MagicMock()
        mock_result = MagicMock()
        mock_document = MagicMock()
        mock_document.export_to_markdown.return_value = "# Test Document\n\nContent"
        mock_result.document = mock_document
        mock_converter.convert.return_value = mock_result
        mock_converter_class.return_value = mock_converter
        
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Create test file
        content = b"Test PDF content"
        test_file = create_test_file(temp_dir, "test.pdf", content)
        
        # Mock database methods
        with patch.object(test_db_manager, 'get_document_by_hash') as mock_get_by_hash, \
             patch.object(test_db_manager, 'create_document') as mock_create_doc, \
             patch.object(test_db_manager, 'update_document_content') as mock_update_content, \
             patch.object(test_db_manager, 'add_document_metadata') as mock_add_metadata, \
             patch.object(test_db_manager, 'log_processing') as mock_log:
            
            # No existing document
            mock_get_by_hash.return_value = None
            
            # Mock created document
            mock_doc = MagicMock()
            mock_doc.id = uuid.uuid4()
            mock_create_doc.return_value = mock_doc
            
            # Process file
            result = await processor.process_file(test_file)
            
            # Verify success
            assert result is True
            
            # Verify database calls
            mock_create_doc.assert_called_once()
            mock_update_content.assert_called_once()
            mock_add_metadata.assert_called_once()
            
            # Verify logging calls (at least one call should be made)
            assert mock_log.call_count >= 1

    @pytest.mark.asyncio
    @patch('doceater.processor.DocumentConverter')
    async def test_process_file_conversion_error(self, mock_converter_class, test_settings, test_db_manager, create_test_file, temp_dir):
        """Test file processing with conversion error."""
        # Setup mock converter to fail
        mock_converter = MagicMock()
        mock_converter.convert.side_effect = Exception("Conversion failed")
        mock_converter_class.return_value = mock_converter
        
        processor = DocumentProcessor(test_settings, test_db_manager)
        
        # Create test file
        content = b"Test PDF content"
        test_file = create_test_file(temp_dir, "test.pdf", content)
        
        # Mock database methods
        with patch.object(test_db_manager, 'get_document_by_hash') as mock_get_by_hash, \
             patch.object(test_db_manager, 'create_document') as mock_create_doc, \
             patch.object(test_db_manager, 'update_document_status') as mock_update_status, \
             patch.object(test_db_manager, 'log_processing') as mock_log:
            
            # No existing document
            mock_get_by_hash.return_value = None
            
            # Mock created document
            mock_doc = MagicMock()
            mock_doc.id = uuid.uuid4()
            mock_create_doc.return_value = mock_doc
            
            # Process file
            result = await processor.process_file(test_file)
            
            # Should return False on error
            assert result is False
            
            # Verify document was marked as failed
            mock_update_status.assert_called_with(mock_doc.id, DocumentStatus.FAILED)
            
            # Verify error was logged
            mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_convert_to_markdown_real_pdf(self, test_settings, test_db_manager, small_pdf_file):
        """Test document conversion with real PDF file (integration test)."""
        processor = DocumentProcessor(test_settings, test_db_manager)

        try:
            # Convert real PDF to markdown
            markdown = await processor.convert_to_markdown(small_pdf_file)

            # Verify conversion produces valid markdown
            assert isinstance(markdown, str)
            assert len(markdown) > 0
            # Real PDFs should produce some content
            assert markdown.strip() != ""

            # Basic markdown structure checks
            # Most PDFs should have some text content
            assert len(markdown.split()) > 0  # Should have at least some words
        except Exception as e:
            # Skip test if Docling models can't be downloaded (e.g., no HF auth)
            if "401" in str(e) or "Unauthorized" in str(e) or "HfHubHTTPError" in str(e):
                pytest.skip(f"Skipping integration test due to Docling model access issue: {e}")
            else:
                raise

    @pytest.mark.asyncio
    async def test_process_file_real_pdf_integration(self, test_settings, test_db_manager, small_pdf_file):
        """Test complete file processing workflow with real PDF (integration test)."""
        processor = DocumentProcessor(test_settings, test_db_manager)

        # Process real PDF file
        result = await processor.process_file(small_pdf_file)

        # Check if processing failed due to Docling model access issues
        if not result:
            # Check if there's a document in the database with failed status
            doc = await test_db_manager.get_document_by_path(str(small_pdf_file))
            if doc and doc.status == DocumentStatus.FAILED:
                # Check the logs to see if it's a model access issue
                logs = await test_db_manager.get_processing_logs(document_id=doc.id)
                for log in logs:
                    if ("401" in log.message or "Unauthorized" in log.message or
                        "HfHubHTTPError" in log.message):
                        pytest.skip("Skipping integration test due to Docling model access issue")
                # If it's a different error, let the test fail normally
                assert False, f"Processing failed for unknown reason. Check logs: {[log.message for log in logs]}"

        # If we get here, processing succeeded
        assert result is True

        # Verify document was created in database
        doc = await test_db_manager.get_document_by_path(str(small_pdf_file))
        assert doc is not None
        assert doc.filename == small_pdf_file.name
        assert doc.status == DocumentStatus.COMPLETED
        assert doc.markdown_content is not None
        assert len(doc.markdown_content) > 0

        # Verify metadata was extracted
        metadata = await test_db_manager.get_document_metadata(doc.id)
        assert metadata is not None
        assert metadata.get("file_extension") == ".pdf"
        assert metadata.get("mime_type") == "application/pdf"

        # Verify processing was logged
        logs = await test_db_manager.get_processing_logs(document_id=doc.id)
        assert len(logs) > 0
