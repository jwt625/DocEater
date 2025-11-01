"""Tests for image serving endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from doceater.models import DocumentImage, ImageType

from .conftest import AsyncContextManagerMock


class TestImageServing:
    """Test cases for image serving endpoint."""

    def test_serve_image_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        temp_dir: Path,
    ):
        """Test successful image serving."""
        image_id = uuid4()

        # Create a test image file
        test_image_path = temp_dir / "test_image.png"
        test_image_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82"
        test_image_path.write_bytes(test_image_content)

        with patch("doceater.api.routes.images.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock session and image record
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )

            mock_image = MagicMock(spec=DocumentImage)
            mock_image.id = image_id
            mock_image.file_path = str(test_image_path)
            mock_image.image_type = ImageType.PICTURE
            mock_image.page_number = 1

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_image
            mock_session.execute.return_value = mock_result

            response = test_client.get(
                f"/api/v1/images/{image_id}", headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "image/png"
            assert "Cache-Control" in response.headers
            assert response.headers["X-Image-Type"] == "picture"
            assert response.headers["X-Page-Number"] == "1"

    def test_serve_image_not_found(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test serving non-existent image."""
        image_id = uuid4()

        with patch("doceater.api.routes.images.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock session with no image found
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            response = test_client.get(
                f"/api/v1/images/{image_id}", headers=auth_headers
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "image not found" in response.json()["detail"].lower()

    def test_serve_image_file_not_on_disk(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test serving image when database record exists but file is missing."""
        image_id = uuid4()
        missing_file_path = "/nonexistent/path/image.png"

        with patch("doceater.api.routes.images.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock session and image record
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )

            mock_image = MagicMock(spec=DocumentImage)
            mock_image.id = image_id
            mock_image.file_path = missing_file_path
            mock_image.image_type = ImageType.PICTURE
            mock_image.page_number = 1

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_image
            mock_session.execute.return_value = mock_result

            response = test_client.get(
                f"/api/v1/images/{image_id}", headers=auth_headers
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "image file not found on disk" in response.json()["detail"].lower()

    def test_serve_image_unauthenticated(self, test_client: TestClient):
        """Test image serving without authentication should fail."""
        image_id = uuid4()

        response = test_client.get(f"/api/v1/images/{image_id}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_serve_image_different_formats(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        temp_dir: Path,
    ):
        """Test serving images with different file formats."""
        test_cases = [
            ("test.jpg", "image/jpeg", b"\xff\xd8\xff\xe0"),  # JPEG header
            ("test.jpeg", "image/jpeg", b"\xff\xd8\xff\xe0"),  # JPEG header
            ("test.webp", "image/webp", b"RIFF"),  # WebP header
            ("test.unknown", "application/octet-stream", b"unknown"),  # Unknown format
        ]

        for filename, expected_mime, content in test_cases:
            image_id = uuid4()
            test_image_path = temp_dir / filename
            test_image_path.write_bytes(content + b"fake_image_data")

            with patch("doceater.api.routes.images.get_db_manager") as mock_get_db:
                mock_db_manager = AsyncMock()
                mock_get_db.return_value = mock_db_manager

                # Mock session and image record
                mock_session = AsyncMock()
                mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                    return_value=mock_session
                )

                mock_image = MagicMock(spec=DocumentImage)
                mock_image.id = image_id
                mock_image.file_path = str(test_image_path)
                mock_image.image_type = ImageType.PICTURE
                mock_image.page_number = 1

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_image
                mock_session.execute.return_value = mock_result

                response = test_client.get(
                    f"/api/v1/images/{image_id}", headers=auth_headers
                )

                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == expected_mime

    def test_serve_image_caching_headers(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        temp_dir: Path,
    ):
        """Test that proper caching headers are set."""
        image_id = uuid4()

        # Create a test image file
        test_image_path = temp_dir / "test_image.png"
        test_image_path.write_bytes(b"fake_png_data")

        with patch("doceater.api.routes.images.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock session and image record
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )

            mock_image = MagicMock(spec=DocumentImage)
            mock_image.id = image_id
            mock_image.file_path = str(test_image_path)
            mock_image.image_type = ImageType.TABLE
            mock_image.page_number = 2

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_image
            mock_session.execute.return_value = mock_result

            response = test_client.get(
                f"/api/v1/images/{image_id}", headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            assert "Cache-Control" in response.headers
            assert "public" in response.headers["Cache-Control"]
            assert "max-age" in response.headers["Cache-Control"]
            assert response.headers["X-Image-Type"] == "table"
            assert response.headers["X-Page-Number"] == "2"

    def test_serve_image_database_error(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        """Test image serving when database query fails."""
        image_id = uuid4()

        with patch("doceater.api.routes.images.get_db_manager") as mock_get_db:
            mock_db_manager = AsyncMock()
            mock_get_db.return_value = mock_db_manager

            # Mock database error
            mock_session = AsyncMock()
            mock_db_manager.get_session = lambda: AsyncContextManagerMock(
                return_value=mock_session
            )
            mock_session.execute.side_effect = Exception("Database error")

            response = test_client.get(
                f"/api/v1/images/{image_id}", headers=auth_headers
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "failed to serve image" in response.json()["detail"].lower()
