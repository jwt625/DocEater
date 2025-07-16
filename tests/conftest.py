"""Pytest configuration and fixtures for DocEater tests."""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from doceater.config import Settings
from doceater.database import DatabaseManager
from doceater.models import Base


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary directories."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        watch_folder=str(temp_dir),
        watch_recursive=True,
        max_file_size_mb=50,  # Increased to handle larger test PDFs
        supported_extensions=[".pdf", ".txt"],
        exclude_patterns=[".*", "~*", "*.tmp"],
        docling_enrich_formula=True,
        max_concurrent_files=2,
        processing_delay_seconds=0.1,
        log_level="DEBUG",
    )


@pytest_asyncio.fixture
async def test_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine."""
    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_db_manager(test_settings: Settings, test_engine: AsyncEngine) -> AsyncGenerator[DatabaseManager, None]:
    """Create a test database manager."""
    db_manager = DatabaseManager(test_settings)
    # Override the engine with our test engine
    db_manager._engine = test_engine
    db_manager._session_factory = None  # Reset to use new engine
    
    yield db_manager
    
    # Clean up
    await db_manager.close()





@pytest.fixture
def sample_text_content() -> str:
    """Create sample text content for testing."""
    return """# Test Document

This is a test document with some content.

## Section 1

Some text content here.

## Section 2

More content with **bold** and *italic* text.

- List item 1
- List item 2
- List item 3

```python
def hello_world():
    print("Hello, World!")
```
"""


@pytest.fixture
def mock_docling() -> MagicMock:
    """Create a mock Docling converter."""
    mock = MagicMock()
    mock.convert.return_value.document.export_to_markdown.return_value = "# Converted Document\n\nMocked content"
    return mock


@pytest.fixture
def mock_file_event() -> MagicMock:
    """Create a mock file system event."""
    mock = MagicMock()
    mock.is_directory = False
    mock.src_path = "/test/path/document.pdf"
    return mock


@pytest.fixture
def sample_document_id() -> uuid.UUID:
    """Create a sample document UUID for testing."""
    return uuid.UUID("12345678-1234-5678-9012-123456789012")


@pytest.fixture
def create_test_file():
    """Factory fixture to create test files."""
    def _create_file(directory: Path, filename: str, content: bytes | str) -> Path:
        file_path = directory / filename
        if isinstance(content, str):
            file_path.write_text(content, encoding="utf-8")
        else:
            file_path.write_bytes(content)
        return file_path

    return _create_file


@pytest.fixture
def test_pdfs_dir() -> Path:
    """Get the test PDFs directory."""
    return Path(__file__).parent.parent / "test_pdfs"


@pytest.fixture
def sample_pdf_files(test_pdfs_dir: Path) -> list[Path]:
    """Get list of sample PDF files for testing."""
    pdf_files = list(test_pdfs_dir.glob("*.pdf"))
    if not pdf_files:
        pytest.skip("No PDF files found in test_pdfs directory")
    return pdf_files


@pytest.fixture
def small_pdf_file(sample_pdf_files: list[Path]) -> Path:
    """Get a small PDF file for testing."""
    if not sample_pdf_files:
        pytest.skip("No PDF files available for testing")

    # Sort by file size and return the smallest one
    pdf_files_with_size = [(f, f.stat().st_size) for f in sample_pdf_files]
    pdf_files_with_size.sort(key=lambda x: x[1])  # Sort by size
    return pdf_files_with_size[0][0]  # Return the smallest file


# Async mock helpers
class AsyncMockContext:
    """Helper for creating async context managers in mocks."""
    
    def __init__(self, return_value: Any = None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, *_):
        return None


def create_async_mock(**kwargs) -> AsyncMock:
    """Create an AsyncMock with common setup."""
    mock = AsyncMock(**kwargs)
    return mock
