"""Tests for configuration management."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from doceater.config import Settings, get_settings


class TestSettings:
    """Test the Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        
        assert settings.database_url == "postgresql://localhost:5432/doceater"
        assert settings.watch_folder == str(Path.home() / "Downloads")
        assert settings.watch_recursive is True
        assert settings.max_file_size_mb == 100
        assert settings.supported_extensions == [".pdf"]
        assert settings.exclude_patterns == [".*", "~*", "*.tmp", "*.temp"]
        assert settings.docling_enrich_formula is True
        assert settings.max_concurrent_files == 3
        assert settings.processing_delay_seconds == 1.0
        assert settings.log_level == "INFO"

    def test_custom_settings(self, temp_dir):
        """Test custom settings values."""
        # Create a custom directory for testing
        custom_path = temp_dir / "custom"
        custom_path.mkdir()

        settings = Settings(
            database_url="postgresql://test:5432/test_db",
            watch_folder=str(custom_path),
            watch_recursive=False,
            max_file_size_mb=50,
            supported_extensions=[".pdf", ".docx"],
            exclude_patterns=["*.backup"],
            docling_enrich_formula=False,
            max_concurrent_files=5,
            processing_delay_seconds=2.0,
            log_level="DEBUG",
        )

        assert settings.database_url == "postgresql://test:5432/test_db"
        assert settings.watch_folder == str(custom_path.resolve())
        assert settings.watch_recursive is False
        assert settings.max_file_size_mb == 50
        assert settings.supported_extensions == [".pdf", ".docx"]
        assert settings.exclude_patterns == ["*.backup"]
        assert settings.docling_enrich_formula is False
        assert settings.max_concurrent_files == 5
        assert settings.processing_delay_seconds == 2.0
        assert settings.log_level == "DEBUG"

    def test_computed_properties(self):
        """Test computed properties."""
        settings = Settings(max_file_size_mb=10)
        
        assert settings.max_file_size_bytes == 10 * 1024 * 1024

    def test_environment_variables(self, monkeypatch, temp_dir):
        """Test loading from environment variables."""
        # Create test directory
        env_path = temp_dir / "env"
        env_path.mkdir()

        # Set environment variables (lists need JSON format for pydantic-settings)
        monkeypatch.setenv("DOCEATER_DATABASE_URL", "postgresql://env:5432/env_db")
        monkeypatch.setenv("DOCEATER_WATCH_FOLDER", str(env_path))
        monkeypatch.setenv("DOCEATER_WATCH_RECURSIVE", "false")
        monkeypatch.setenv("DOCEATER_MAX_FILE_SIZE_MB", "25")
        monkeypatch.setenv("DOCEATER_SUPPORTED_EXTENSIONS", '["pdf", ".docx", ".txt"]')
        monkeypatch.setenv("DOCEATER_EXCLUDE_PATTERNS", '["*.bak", "*.old"]')
        monkeypatch.setenv("DOCEATER_DOCLING_ENRICH_FORMULA", "false")
        monkeypatch.setenv("DOCEATER_MAX_CONCURRENT_FILES", "7")
        monkeypatch.setenv("DOCEATER_PROCESSING_DELAY_SECONDS", "0.5")
        monkeypatch.setenv("DOCEATER_LOG_LEVEL", "WARNING")

        settings = Settings()

        assert settings.database_url == "postgresql://env:5432/env_db"
        assert settings.watch_folder == str(env_path.resolve())
        assert settings.watch_recursive is False
        assert settings.max_file_size_mb == 25
        assert settings.supported_extensions == ["pdf", ".docx", ".txt"]
        assert settings.exclude_patterns == ["*.bak", "*.old"]
        assert settings.docling_enrich_formula is False
        assert settings.max_concurrent_files == 7
        assert settings.processing_delay_seconds == 0.5
        assert settings.log_level == "WARNING"

    def test_env_file_loading(self, tmp_path):
        """Test loading from .env file."""
        # Create test directory
        file_path = tmp_path / "file"
        file_path.mkdir()

        env_file = tmp_path / ".env"
        env_file.write_text(f"""
DOCEATER_DATABASE_URL=postgresql://file:5432/file_db
DOCEATER_WATCH_FOLDER={file_path}
DOCEATER_MAX_FILE_SIZE_MB=15
DOCEATER_LOG_LEVEL=ERROR
""")

        # Change to the temp directory so .env is found
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings()

            assert settings.database_url == "postgresql://file:5432/file_db"
            assert settings.watch_folder == str(file_path.resolve())
            assert settings.max_file_size_mb == 15
            assert settings.log_level == "ERROR"
        finally:
            os.chdir(original_cwd)

    def test_validation_errors(self):
        """Test validation errors for invalid values."""
        with pytest.raises(ValidationError):
            Settings(max_file_size_mb=-1)

        with pytest.raises(ValidationError):
            Settings(max_file_size_mb=1001)  # Over 1000MB limit

        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")

    def test_case_insensitive_env_vars(self, monkeypatch, temp_dir):
        """Test that environment variables are case insensitive."""
        # Create test directory
        upper_path = temp_dir / "upper"
        upper_path.mkdir()

        monkeypatch.setenv("doceater_database_url", "postgresql://lower:5432/test")
        monkeypatch.setenv("DOCEATER_WATCH_FOLDER", str(upper_path))

        settings = Settings()

        assert settings.database_url == "postgresql://lower:5432/test"
        assert settings.watch_folder == str(upper_path.resolve())

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored."""
        # This should not raise an error
        settings = Settings(unknown_field="value", another_unknown=123)
        
        # Unknown fields should be ignored
        assert not hasattr(settings, "unknown_field")
        assert not hasattr(settings, "another_unknown")


class TestGetSettings:
    """Test the get_settings function."""

    def test_get_settings_singleton(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2

    def test_get_settings_with_reload(self, monkeypatch):
        """Test get_settings with reload."""
        from doceater.config import reload_settings

        # Get initial settings
        settings1 = get_settings()
        initial_db_url = settings1.database_url

        # Change environment variable
        monkeypatch.setenv("DOCEATER_DATABASE_URL", "postgresql://new:5432/new_db")

        # Get settings without reload - should be same
        settings2 = get_settings()
        assert settings2.database_url == initial_db_url

        # Reload settings - should be different
        settings3 = reload_settings()
        assert settings3.database_url == "postgresql://new:5432/new_db"

        # Subsequent calls should return the new instance
        settings4 = get_settings()
        assert settings4 is settings3
