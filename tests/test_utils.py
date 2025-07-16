"""Test utilities and helpers for DocEater tests."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any





def create_test_text_file(content: str = "Test content") -> str:
    """Create test text content."""
    return content


def calculate_content_hash(content: bytes | str) -> str:
    """Calculate SHA-256 hash of content."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


def create_temp_file(directory: Path, filename: str, content: bytes | str) -> Path:
    """Create a temporary file with given content."""
    file_path = directory / filename
    if isinstance(content, str):
        file_path.write_text(content, encoding="utf-8")
    else:
        file_path.write_bytes(content)
    return file_path


class MockAsyncContextManager:
    """Mock async context manager for testing."""
    
    def __init__(self, return_value: Any = None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def assert_file_exists(file_path: Path) -> None:
    """Assert that a file exists."""
    assert file_path.exists(), f"File does not exist: {file_path}"


def assert_file_not_exists(file_path: Path) -> None:
    """Assert that a file does not exist."""
    assert not file_path.exists(), f"File should not exist: {file_path}"


def assert_file_content(file_path: Path, expected_content: str) -> None:
    """Assert that a file contains expected content."""
    assert_file_exists(file_path)
    actual_content = file_path.read_text(encoding="utf-8")
    assert actual_content == expected_content, f"File content mismatch in {file_path}"


def assert_file_size(file_path: Path, expected_size: int) -> None:
    """Assert that a file has expected size."""
    assert_file_exists(file_path)
    actual_size = file_path.stat().st_size
    assert actual_size == expected_size, f"File size mismatch: expected {expected_size}, got {actual_size}"


# Common test data
SAMPLE_MARKDOWN = """# Test Document

This is a test document for DocEater.

## Section 1

Some content here with **bold** and *italic* text.

## Section 2

- List item 1
- List item 2
- List item 3

```python
def hello():
    print("Hello, World!")
```

## Conclusion

This is the end of the test document.
"""

SAMPLE_METADATA = {
    "title": "Test Document",
    "author": "Test Author",
    "subject": "Testing",
    "keywords": "test, document, pdf",
    "creator": "DocEater Test Suite",
    "producer": "Test Producer",
    "creation_date": "2024-01-01T00:00:00Z",
    "modification_date": "2024-01-01T00:00:00Z",
}

# File extensions for testing
SUPPORTED_EXTENSIONS = [".pdf", ".txt", ".md"]
UNSUPPORTED_EXTENSIONS = [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]

# Test file patterns
EXCLUDE_PATTERNS = [".*", "~*", "*.tmp", "*.temp", "*.bak"]
