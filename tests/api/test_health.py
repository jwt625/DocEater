"""Tests for health check and system status endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from .conftest import AsyncContextManagerMock


class TestHealthEndpoint:
    """Test cases for the health check endpoint."""

    def test_health_check_success(self, test_client: TestClient):
        """Test successful health check without authentication."""
        with patch("doceater.api.routes.health.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock session for health check
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )

            response = test_client.get("/api/v1/health")

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()

            assert "status" in response_data
            assert "timestamp" in response_data
            assert "version" in response_data
            assert "database" in response_data
            assert "embedding_model" in response_data
            assert "disk_space" in response_data
            assert "uptime_seconds" in response_data
            assert "memory_usage_mb" in response_data

            assert response_data["database"] == "healthy"

    def test_health_check_database_failure(self, test_client: TestClient):
        """Test health check when database is unavailable."""
        with patch("doceater.api.routes.health.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock database connection failure
            failed_context = AsyncContextManagerMock(
                side_effect=Exception("Database connection failed")
            )
            # Use a lambda to return the context manager directly, not wrapped in AsyncMock
            mock_db_manager.get_session = lambda: failed_context

            response = test_client.get("/api/v1/health")

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()

            assert response_data["database"] == "unhealthy"
            assert response_data["status"] == "unhealthy"

    def test_health_check_with_authentication(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test health check with authentication (should still work)."""
        with patch("doceater.api.routes.health.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock successful database connection with proper async context manager
            mock_session = AsyncMock()
            mock_context_manager = AsyncContextManagerMock(return_value=mock_session)
            # Use a lambda to return the context manager directly, not wrapped in AsyncMock
            mock_db_manager.get_session = lambda: mock_context_manager
            mock_session.execute.return_value = None

            response = test_client.get("/api/v1/health", headers=auth_headers)

            assert response.status_code == status.HTTP_200_OK


class TestStatsEndpoint:
    """Test cases for the system statistics endpoint."""

    def test_stats_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test successful stats retrieval with authentication."""
        with patch("doceater.api.routes.health.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock session and query results
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )

            # Mock query results for statistics
            mock_result = MagicMock()
            mock_result.scalar.return_value = 10  # Mock count results
            mock_session.execute.return_value = mock_result

            response = test_client.get("/api/v1/stats", headers=auth_headers)

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()

            # Verify all required fields are present
            required_fields = [
                "total_documents",
                "processing_documents",
                "failed_documents",
                "total_text_embeddings",
                "total_image_embeddings",
                "total_images",
                "total_storage_mb",
                "database_size_mb",
                "images_storage_mb",
                "avg_processing_time_seconds",
                "avg_search_time_ms",
            ]

            for field in required_fields:
                assert field in response_data

    def test_stats_unauthenticated(self, test_client: TestClient):
        """Test stats endpoint without authentication should fail."""
        response = test_client.get("/api/v1/stats")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_stats_database_error(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test stats endpoint when database query fails."""
        with patch("doceater.api.routes.health.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock database error
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )
            mock_session.execute.side_effect = Exception("Query failed")

            response = test_client.get("/api/v1/stats", headers=auth_headers)

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
