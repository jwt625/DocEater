"""API test fixtures and configuration."""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

from doceater.api.auth import create_jwt_token
from doceater.api.main import create_app
from doceater.config import Settings
from doceater.database import DatabaseManager


@pytest.fixture
def api_test_settings(temp_dir: Path) -> Settings:
    """Create test settings for API testing with PostgreSQL."""
    return Settings(
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/doceater",
        # API settings
        api_host="127.0.0.1",
        api_port=8000,
        require_auth=True,
        allow_anonymous_health=True,
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_expiration_hours=24,
        api_keys="test-api-key:test-user",
        # File upload settings
        upload_max_size_mb=100,
        upload_chunk_size_kb=64,
        upload_timeout_seconds=300,
        temp_upload_dir=str(temp_dir / "uploads"),
        cleanup_temp_files=True,
        # CORS settings
        cors_origins="*",
        cors_methods="GET,POST,PUT,DELETE",
        cors_headers="*",
        # Other settings
        watch_folder=str(temp_dir),
        max_file_size_mb=100,
        supported_extensions=[".pdf"],
        exclude_patterns=[".*", "~*", "*.tmp"],
        log_level="DEBUG",
        images_base_path=str(temp_dir / "images"),
    )


@pytest.fixture
def test_app(api_test_settings: Settings):
    """Create a test FastAPI application."""
    with patch("doceater.api.main.get_settings", return_value=api_test_settings):
        app = create_app()
        return app


@pytest.fixture
def test_client(test_app) -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(test_app)


@pytest_asyncio.fixture
async def async_test_client(test_app) -> AsyncGenerator[AsyncClient]:
    """Create an async test client for the FastAPI application."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def valid_jwt_token(api_test_settings: Settings) -> str:
    """Create a valid JWT token for testing."""
    from doceater.api.auth import init_auth_config

    # Initialize auth config with test settings
    init_auth_config(api_test_settings)

    return create_jwt_token(
        user_id="test-user", username="test-user", scopes=["read", "write"]
    )


@pytest.fixture
def read_only_jwt_token(api_test_settings: Settings) -> str:
    """Create a read-only JWT token for testing."""
    from doceater.api.auth import init_auth_config

    # Initialize auth config with test settings
    init_auth_config(api_test_settings)

    return create_jwt_token(
        user_id="readonly-user", username="readonly-user", scopes=["read"]
    )


@pytest.fixture
def valid_api_key() -> str:
    """Return a valid API key for testing."""
    return "test-api-key"


@pytest.fixture
def auth_headers(valid_jwt_token: str) -> dict[str, str]:
    """Create authorization headers with JWT token."""
    return {"Authorization": f"Bearer {valid_jwt_token}"}


@pytest.fixture
def api_key_headers(valid_api_key: str) -> dict[str, str]:
    """Create authorization headers with API key."""
    return {"Authorization": f"Bearer {valid_api_key}"}


@pytest.fixture
def read_only_headers(read_only_jwt_token: str) -> dict[str, str]:
    """Create authorization headers with read-only token."""
    return {"Authorization": f"Bearer {read_only_jwt_token}"}


@pytest.fixture
def mock_document_processor():
    """Mock the document processor to avoid actual processing."""
    with patch("doceater.api.routes.documents.DocumentProcessor") as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_db_manager():
    """Mock the database manager for isolated testing."""
    with patch("doceater.api.routes.documents.get_db_manager") as mock:
        mock_manager = AsyncMock(spec=DatabaseManager)

        # Create a proper async context manager for get_session
        mock_session = AsyncMock()
        # get_session is an async context manager, so we need to mock it properly
        mock_manager.get_session = lambda: AsyncContextManagerMock(
            return_value=mock_session
        )

        mock.return_value = mock_manager
        yield mock_manager


@pytest.fixture
def create_test_pdf():
    """Factory fixture to create test PDF files."""

    def _create_pdf(size_mb: float = 0.1, filename: str = "test.pdf") -> bytes:
        """Create a test PDF file of specified size."""
        # Create a minimal PDF structure
        pdf_header = b"%PDF-1.4\n"
        pdf_content = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        pdf_content += b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        pdf_content += b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"

        # Add padding to reach desired size
        target_size = int(size_mb * 1024 * 1024)
        current_size = len(pdf_header) + len(pdf_content)

        if target_size > current_size:
            padding_size = target_size - current_size - 20  # Leave room for trailer
            padding = b"%" + b"X" * padding_size + b"\n"
        else:
            padding = b""

        pdf_trailer = b"xref\n0 4\n0000000000 65535 f \n"
        pdf_trailer += b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"

        return pdf_header + pdf_content + padding + pdf_trailer

    return _create_pdf


@pytest.fixture
def small_test_pdf(create_test_pdf) -> bytes:
    """Create a small test PDF (100KB)."""
    return create_test_pdf(size_mb=0.1)


@pytest.fixture
def large_test_pdf(create_test_pdf) -> bytes:
    """Create a large test PDF (101MB - over the limit)."""
    return create_test_pdf(size_mb=101)


@pytest.fixture
def temp_upload_dir(api_test_settings: Settings) -> Path:
    """Create and return the temporary upload directory."""
    upload_dir = Path(api_test_settings.temp_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


class AsyncContextManagerMock:
    """Helper class for mocking async context managers."""

    def __init__(self, return_value=None, side_effect=None):
        self.return_value = return_value
        self.side_effect = side_effect

    async def __aenter__(self):
        if self.side_effect:
            raise self.side_effect
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.fixture
def mock_async_session():
    """Create a mock async session."""
    session = AsyncMock()
    session.execute.return_value = None
    return session


@pytest.fixture
def mock_db_session_context(mock_async_session):
    """Create a mock database session context manager."""
    return AsyncContextManagerMock(return_value=mock_async_session)
