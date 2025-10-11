"""Tests for authentication and authorization."""

import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from doceater.api.auth import create_jwt_token, verify_jwt_token, TokenData


class TestJWTAuthentication:
    """Test cases for JWT token authentication."""

    def test_create_jwt_token(self, api_test_settings):
        """Test JWT token creation."""
        from doceater.api.auth import init_auth_config

        # Initialize auth config with test settings
        init_auth_config(api_test_settings)

        token = create_jwt_token(
            user_id="test-user",
            username="test-user",
            scopes=["read", "write"]
        )

        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token can be decoded
        payload = jwt.decode(
            token,
            api_test_settings.jwt_secret_key,
            algorithms=[api_test_settings.jwt_algorithm]
        )

        assert payload["user_id"] == "test-user"
        assert payload["username"] == "test-user"
        assert payload["scopes"] == ["read", "write"]

    def test_verify_jwt_token_valid(self, api_test_settings):
        """Test verification of valid JWT token."""
        from doceater.api.auth import init_auth_config

        # Initialize auth config with test settings
        init_auth_config(api_test_settings)

        token = create_jwt_token(
            user_id="test-user",
            username="test-user",
            scopes=["read", "write"]
        )

        token_data = verify_jwt_token(token)

        assert isinstance(token_data, TokenData)
        assert token_data.user_id == "test-user"
        assert token_data.username == "test-user"
        assert token_data.scopes == ["read", "write"]

    def test_verify_jwt_token_expired(self, api_test_settings):
        """Test verification of expired JWT token."""
        # Create token with past expiration
        now = datetime.now(timezone.utc)
        exp = now - timedelta(hours=1)  # Expired 1 hour ago
        
        payload = {
            "user_id": "test-user",
            "username": "test-user",
            "scopes": ["read", "write"],
            "exp": exp,
            "iat": now - timedelta(hours=2),
        }
        
        expired_token = jwt.encode(
            payload,
            api_test_settings.jwt_secret_key,
            algorithm=api_test_settings.jwt_algorithm
        )
        
        with patch("doceater.api.auth.auth_config") as mock_config:
            mock_config.jwt_secret_key = api_test_settings.jwt_secret_key
            mock_config.jwt_algorithm = api_test_settings.jwt_algorithm
            
            with pytest.raises(Exception) as exc_info:
                verify_jwt_token(expired_token)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "expired" in str(exc_info.value.detail).lower()

    def test_verify_jwt_token_invalid(self, api_test_settings):
        """Test verification of invalid JWT token."""
        invalid_token = "invalid.jwt.token"
        
        with patch("doceater.api.auth.auth_config") as mock_config:
            mock_config.jwt_secret_key = api_test_settings.jwt_secret_key
            mock_config.jwt_algorithm = api_test_settings.jwt_algorithm
            
            with pytest.raises(Exception) as exc_info:
                verify_jwt_token(invalid_token)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestAPIKeyAuthentication:
    """Test cases for API key authentication."""

    def test_api_key_authentication_success(
        self,
        test_client: TestClient,
        small_test_pdf: bytes,
        api_test_settings,
    ):
        """Test successful API key authentication."""
        import io
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4
        from doceater.models import Document, DocumentStatus
        from doceater.api.auth import init_auth_config

        # Initialize auth config with test settings
        init_auth_config(api_test_settings)

        with patch("doceater.api.routes.documents.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager
            
            # Mock document creation
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
            headers = {"Authorization": "Bearer test-api-key"}
            
            response = test_client.post(
                "/api/v1/documents/upload",
                files=files,
                headers=headers,
            )
            
            assert response.status_code == status.HTTP_200_OK

    def test_api_key_authentication_invalid(
        self,
        test_client: TestClient,
        small_test_pdf: bytes,
    ):
        """Test invalid API key authentication."""
        import io
        
        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        headers = {"Authorization": "Bearer invalid-api-key"}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=headers,
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestScopeBasedPermissions:
    """Test cases for scope-based permissions."""

    def test_read_scope_access_get_endpoints(
        self,
        test_client: TestClient,
        read_only_headers: dict[str, str],
    ):
        """Test that read scope allows access to GET endpoints."""
        with patch("doceater.api.routes.health.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager
            
            # Mock session and query results
            mock_session = AsyncMock()
            mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session
            
            # Mock query results
            mock_result = MagicMock()
            mock_result.scalar.return_value = 0
            mock_session.execute.return_value = mock_result
            mock_result.scalars.return_value.all.return_value = []
            
            response = test_client.get("/api/v1/documents", headers=read_only_headers)
            
            assert response.status_code == status.HTTP_200_OK

    def test_read_scope_denied_write_endpoints(
        self,
        test_client: TestClient,
        read_only_headers: dict[str, str],
        small_test_pdf: bytes,
    ):
        """Test that read scope is denied access to write endpoints."""
        import io
        
        files = {"file": ("test.pdf", io.BytesIO(small_test_pdf), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=read_only_headers,
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "insufficient permissions" in response.json()["detail"].lower()

    def test_write_scope_access_all_endpoints(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        small_test_pdf: bytes,
    ):
        """Test that write scope allows access to all endpoints."""
        import io
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4
        from doceater.models import Document, DocumentStatus
        
        with patch("doceater.api.routes.documents.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager
            
            # Mock document creation
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
                headers=auth_headers,
            )
            
            assert response.status_code == status.HTTP_200_OK


class TestAuthenticationDisabled:
    """Test cases for when authentication is disabled."""

    def test_anonymous_access_when_auth_disabled(self, test_client: TestClient):
        """Test anonymous access when authentication is disabled."""
        with patch("doceater.api.auth.auth_config") as mock_config:
            mock_config.require_auth = False
            
            response = test_client.get("/api/v1/health")
            
            assert response.status_code == status.HTTP_200_OK
