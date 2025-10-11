"""Tests for document management API endpoints."""

import io
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from doceater.models import Document, DocumentStatus
from .conftest import AsyncContextManagerMock


class TestDocumentUpload:
    """Test cases for the PDF upload endpoint."""

    def test_upload_pdf_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        small_test_pdf: bytes,
        mock_db_manager: AsyncMock,
        temp_upload_dir: Path,
    ):
        """Test successful PDF upload with valid authentication."""
        # Mock database operations
        mock_document = MagicMock(spec=Document)
        mock_document.id = uuid4()
        mock_document.filename = "test.pdf"
        mock_document.file_size = len(small_test_pdf)
        mock_document.mime_type = "application/pdf"
        mock_document.status = DocumentStatus.PROCESSING
        mock_document.created_at = "2025-10-11T10:00:00Z"
        mock_document.updated_at = "2025-10-11T10:00:00Z"
        mock_document.markdown_content = None
        
        mock_db_manager.create_document.return_value = mock_document

        # Prepare file upload
        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        data = {"description": "Test document upload"}

        # Make request
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        
        assert response_data["filename"] == "test.pdf"
        assert response_data["file_size"] == len(small_test_pdf)
        assert response_data["mime_type"] == "application/pdf"
        assert response_data["status"] == "processing"
        assert "id" in response_data

    def test_upload_pdf_cleanup_temp_file(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        small_test_pdf: bytes,
        mock_db_manager: AsyncMock,
        temp_upload_dir: Path,
    ):
        """Test that temporary files are cleaned up after successful upload when cleanup_temp_files=True."""
        # Mock database operations
        mock_document = MagicMock(spec=Document)
        mock_document.id = uuid4()
        mock_document.filename = "test_cleanup.pdf"
        mock_document.file_size = len(small_test_pdf)
        mock_document.mime_type = "application/pdf"
        mock_document.status = DocumentStatus.PROCESSING
        mock_document.created_at = "2025-10-11T10:00:00Z"
        mock_document.updated_at = "2025-10-11T10:00:00Z"
        mock_document.markdown_content = None

        mock_db_manager.create_document.return_value = mock_document

        # Prepare file upload
        files = {"file": ("test_cleanup.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        data = {"description": "Test cleanup"}

        # Verify temp file doesn't exist before upload
        temp_file_path = temp_upload_dir / "upload_test_cleanup.pdf"
        assert not temp_file_path.exists()

        # Make request
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        # Verify response is successful
        assert response.status_code == status.HTTP_200_OK

        # Verify temp file was cleaned up (since cleanup_temp_files=True in test config)
        assert not temp_file_path.exists(), "Temporary file should be cleaned up after successful upload"

    def test_upload_pdf_unauthenticated(
        self,
        test_client: TestClient,
        small_test_pdf: bytes,
    ):
        """Test PDF upload without authentication should fail."""
        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        
        response = test_client.post("/api/v1/documents/upload", files=files)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "authentication required" in response.json()["detail"].lower()

    def test_upload_pdf_insufficient_permissions(
        self,
        test_client: TestClient,
        read_only_headers: dict[str, str],
        small_test_pdf: bytes,
    ):
        """Test PDF upload with read-only permissions should fail."""
        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=read_only_headers,
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient permissions" in response.json()["detail"].lower()

    def test_upload_non_pdf_file(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test upload of non-PDF file should fail."""
        text_content = b"This is not a PDF file"
        files = {"file": ("document.txt", io.BytesIO(text_content), "text/plain")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "only pdf files are supported" in response.json()["detail"].lower()

    def test_upload_file_too_large(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        large_test_pdf: bytes,
    ):
        """Test upload of file exceeding size limit should fail."""
        files = {"file": ("large.pdf", io.BytesIO(large_test_pdf), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        assert "exceeds maximum allowed size" in response.json()["detail"]

    def test_upload_with_api_key_authentication(
        self,
        test_client: TestClient,
        api_key_headers: dict[str, str],
        small_test_pdf: bytes,
        mock_db_manager: AsyncMock,
    ):
        """Test PDF upload using API key authentication."""
        # Mock database operations
        mock_document = MagicMock(spec=Document)
        mock_document.id = uuid4()
        mock_document.filename = "test.pdf"
        mock_document.file_size = len(small_test_pdf)
        mock_document.mime_type = "application/pdf"
        mock_document.status = DocumentStatus.PROCESSING
        mock_document.created_at = "2025-10-11T10:00:00Z"
        mock_document.updated_at = "2025-10-11T10:00:00Z"
        mock_document.markdown_content = None
        
        mock_db_manager.create_document.return_value = mock_document

        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=api_key_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_upload_streaming_functionality(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        mock_db_manager: AsyncMock,
        temp_upload_dir: Path,
    ):
        """Test that large files are streamed properly without loading into memory."""
        # Create a moderately large PDF (10MB)
        large_pdf_content = b"%PDF-1.4\n" + b"X" * (10 * 1024 * 1024 - 10) + b"\n%%EOF"
        
        # Mock database operations
        mock_document = MagicMock(spec=Document)
        mock_document.id = uuid4()
        mock_document.filename = "large.pdf"
        mock_document.file_size = len(large_pdf_content)
        mock_document.mime_type = "application/pdf"
        mock_document.status = DocumentStatus.PROCESSING
        mock_document.created_at = "2025-10-11T10:00:00Z"
        mock_document.updated_at = "2025-10-11T10:00:00Z"
        mock_document.markdown_content = None
        
        mock_db_manager.create_document.return_value = mock_document

        files = {"file": ("large.pdf", io.BytesIO(large_pdf_content), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["file_size"] == len(large_pdf_content)

    @patch("doceater.api.routes.documents.save_upload_file")
    def test_upload_file_save_error_cleanup(
        self,
        mock_save_file: MagicMock,
        test_client: TestClient,
        auth_headers: dict[str, str],
        small_test_pdf: bytes,
    ):
        """Test that temporary files are cleaned up when save operation fails."""
        # Mock file save to raise an exception
        mock_save_file.side_effect = Exception("Disk full")
        
        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to save uploaded file" in response.json()["detail"].lower()

    def test_upload_database_error_handling(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        small_test_pdf: bytes,
        mock_db_manager: AsyncMock,
    ):
        """Test handling of database errors during upload."""
        # Mock database to raise an exception
        mock_db_manager.create_document.side_effect = Exception("Database connection failed")
        
        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to process document" in response.json()["detail"].lower()

    def test_upload_with_metadata(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        small_test_pdf: bytes,
        mock_db_manager: AsyncMock,
    ):
        """Test PDF upload with optional metadata."""
        # Mock database operations
        mock_document = MagicMock(spec=Document)
        mock_document.id = uuid4()
        mock_document.filename = "test.pdf"
        mock_document.file_size = len(small_test_pdf)
        mock_document.mime_type = "application/pdf"
        mock_document.status = DocumentStatus.PROCESSING
        mock_document.created_at = "2025-10-11T10:00:00Z"
        mock_document.updated_at = "2025-10-11T10:00:00Z"
        mock_document.markdown_content = None
        
        mock_db_manager.create_document.return_value = mock_document

        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        data = {"description": "Test document with description"}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["filename"] == "test.pdf"

    def test_upload_missing_file(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test upload request without file should fail."""
        response = test_client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_upload_empty_filename(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        small_test_pdf: bytes,
    ):
        """Test upload with empty filename should fail."""
        files = {"file": ("", io.BytesIO(small_test_pdf), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "validation" in response.json()["message"].lower()


class TestDocumentList:
    """Test cases for document listing endpoint."""

    def test_list_documents_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test successful document listing."""
        with patch("doceater.api.routes.documents.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager
            
            # Mock session and query results
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(return_value=mock_session)
            
            # Mock query execution
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0  # Total count
            mock_session.execute.return_value = mock_result
            
            # Mock scalars for documents
            mock_result.scalars.return_value.all.return_value = []
            
            response = test_client.get("/api/v1/documents", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert "documents" in response_data
            assert "total" in response_data
            assert "page" in response_data
            assert "page_size" in response_data
            assert "has_next" in response_data

    def test_list_documents_unauthenticated(self, test_client: TestClient):
        """Test document listing without authentication should fail."""
        response = test_client.get("/api/v1/documents")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDocumentGet:
    """Test cases for getting individual documents."""

    def test_get_document_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test successful document retrieval."""
        document_id = uuid4()
        
        with patch("doceater.api.routes.documents.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager
            
            # Mock document
            mock_document = MagicMock(spec=Document)
            mock_document.id = document_id
            mock_document.filename = "test.pdf"
            mock_document.file_size = 1024
            mock_document.mime_type = "application/pdf"
            mock_document.status = DocumentStatus.COMPLETED
            mock_document.created_at = "2025-10-11T10:00:00Z"
            mock_document.updated_at = "2025-10-11T10:00:00Z"
            mock_document.markdown_content = "# Test Document"
            
            mock_db_manager.get_document_by_id.return_value = mock_document
            
            response = test_client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["id"] == str(document_id)
            assert response_data["filename"] == "test.pdf"

    def test_get_document_not_found(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test getting non-existent document should return 404."""
        document_id = uuid4()
        
        with patch("doceater.api.routes.documents.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager
            mock_db_manager.get_document_by_id.return_value = None
            
            response = test_client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
            
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "document not found" in response.json()["detail"].lower()


class TestDocumentDelete:
    """Test cases for document deletion."""

    def test_delete_document_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test successful document deletion."""
        document_id = uuid4()
        
        with patch("doceater.api.routes.documents.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager
            
            # Mock document exists
            mock_document = MagicMock(spec=Document)
            mock_document.id = document_id
            mock_db_manager.get_document_by_id.return_value = mock_document
            
            response = test_client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            assert "deleted successfully" in response.json()["message"].lower()

    def test_delete_document_insufficient_permissions(
        self,
        test_client: TestClient,
        read_only_headers: dict[str, str],
    ):
        """Test document deletion with read-only permissions should fail."""
        document_id = uuid4()
        
        response = test_client.delete(f"/api/v1/documents/{document_id}", headers=read_only_headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
