"""Tests for CLI commands."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from doceater.cli import app
from doceater.models import DocumentStatus, ImageType


class TestCLIInfrastructure:
    """Test CLI infrastructure and setup."""

    def test_cli_app_creation(self):
        """Test that CLI app is properly created."""
        assert isinstance(app, typer.Typer)
        assert app.info.name == "doceat"
        assert "DocEater" in app.info.help


@pytest.fixture
def cli_runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings for CLI tests."""
    settings = MagicMock()
    settings.watch_folder = "/test/watch/folder"
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.log_level = "INFO"
    settings.log_file = None  # Explicitly set to None to avoid file creation
    settings.images_enabled = True
    return settings


@pytest.fixture
def mock_db_manager():
    """Create mock database manager for CLI tests."""
    db_manager = AsyncMock()
    
    # Mock document data
    mock_doc = MagicMock()
    mock_doc.id = uuid.UUID("12345678-1234-5678-9012-123456789012")
    mock_doc.filename = "test.pdf"
    mock_doc.file_path = "/test/path/test.pdf"
    mock_doc.status = DocumentStatus.COMPLETED
    mock_doc.file_size = 1024 * 1024  # 1MB
    mock_doc.created_at.strftime.return_value = "2025-01-01 12:00"
    mock_doc.processed_at = None
    mock_doc.mime_type = "application/pdf"
    mock_doc.markdown_content = "# Test Document\n\nContent here..."
    
    db_manager.get_document_by_id.return_value = mock_doc
    db_manager.list_documents.return_value = [mock_doc]
    db_manager.create_tables.return_value = None
    db_manager.drop_tables.return_value = None
    db_manager.close.return_value = None
    
    # Mock image data
    mock_image = MagicMock()
    mock_image.document_id = mock_doc.id
    mock_image.image_type = ImageType.PICTURE
    mock_image.filename = "test_image.png"
    mock_image.file_size = 512 * 1024  # 512KB
    mock_image.width = 800
    mock_image.height = 600
    mock_image.image_index = 1
    mock_image.created_at.strftime.return_value = "2025-01-01 12:00"
    
    db_manager.get_document_images.return_value = [mock_image]
    db_manager.get_images_by_type.return_value = [mock_image]
    
    return db_manager


@pytest.fixture
def mock_file_watcher():
    """Create mock file watcher for CLI tests."""
    watcher = AsyncMock()
    watcher.start_watching.return_value = None
    watcher.stop_watching.return_value = None
    watcher.process_existing_files.return_value = None
    watcher.manual_process_file.return_value = True
    return watcher


@pytest.fixture
def mock_image_storage():
    """Create mock image storage manager for CLI tests."""
    storage = MagicMock()
    storage.get_storage_stats.return_value = {
        "base_path": "/test/images",
        "total_files": 10,
        "total_size_mb": 5.5
    }
    return storage


class TestVersionCommand:
    """Test version command."""

    def test_version_command(self, cli_runner):
        """Test version command output."""
        result = cli_runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "DocEater version" in result.stdout


class TestInitCommand:
    """Test init command."""

    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_init_command_success(self, mock_get_settings, mock_get_db_manager, 
                                  cli_runner, mock_settings, mock_db_manager):
        """Test successful database initialization."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        
        result = cli_runner.invoke(app, ["init"])
        
        assert result.exit_code == 0
        assert "Initializing DocEater" in result.stdout
        assert "Database initialized successfully" in result.stdout
        mock_db_manager.create_tables.assert_called_once()
        mock_db_manager.close.assert_called_once()

    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_init_command_with_force(self, mock_get_settings, mock_get_db_manager,
                                     cli_runner, mock_settings, mock_db_manager):
        """Test database initialization with force flag."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        
        result = cli_runner.invoke(app, ["init", "--force"])
        
        assert result.exit_code == 0
        assert "Dropping existing tables" in result.stdout
        mock_db_manager.drop_tables.assert_called_once()
        mock_db_manager.create_tables.assert_called_once()

    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_init_command_failure(self, mock_get_settings, mock_get_db_manager,
                                  cli_runner, mock_settings):
        """Test database initialization failure."""
        mock_get_settings.return_value = mock_settings
        mock_db_manager = AsyncMock()
        mock_db_manager.create_tables.side_effect = Exception("Database error")
        mock_get_db_manager.return_value = mock_db_manager
        
        result = cli_runner.invoke(app, ["init"])
        
        assert result.exit_code == 1
        assert "Failed to initialize database" in result.stdout


class TestWatchCommand:
    """Test watch command."""

    @patch("doceater.cli.FileWatcher")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_watch_command_basic(self, mock_get_settings, mock_get_db_manager,
                                 mock_watcher_class, cli_runner, mock_settings, 
                                 mock_db_manager, mock_file_watcher):
        """Test basic watch command."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        mock_watcher_class.return_value = mock_file_watcher
        
        # Mock asyncio.sleep to prevent infinite loop
        with patch("doceater.cli.asyncio.sleep", side_effect=KeyboardInterrupt):
            result = cli_runner.invoke(app, ["watch"])
        
        assert result.exit_code == 0
        assert "Starting file watcher" in result.stdout
        assert "Stopping file watcher" in result.stdout
        mock_file_watcher.start_watching.assert_called_once()
        mock_file_watcher.stop_watching.assert_called_once()

    @patch("doceater.cli.FileWatcher")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_watch_command_with_folder(self, mock_get_settings, mock_get_db_manager,
                                       mock_watcher_class, cli_runner, mock_settings,
                                       mock_db_manager, mock_file_watcher):
        """Test watch command with custom folder."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        mock_watcher_class.return_value = mock_file_watcher
        
        with patch("doceater.cli.asyncio.sleep", side_effect=KeyboardInterrupt):
            result = cli_runner.invoke(app, ["watch", "/custom/folder"])
        
        assert result.exit_code == 0
        # Settings should be modified with custom folder
        assert mock_settings.watch_folder != "/test/watch/folder"

    @patch("doceater.cli.FileWatcher")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_watch_command_process_existing(self, mock_get_settings, mock_get_db_manager,
                                            mock_watcher_class, cli_runner, mock_settings,
                                            mock_db_manager, mock_file_watcher):
        """Test watch command with process-existing flag."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        mock_watcher_class.return_value = mock_file_watcher
        
        with patch("doceater.cli.asyncio.sleep", side_effect=KeyboardInterrupt):
            result = cli_runner.invoke(app, ["watch", "--process-existing"])
        
        assert result.exit_code == 0
        assert "Processing existing files" in result.stdout
        mock_file_watcher.process_existing_files.assert_called_once()


class TestIngestCommand:
    """Test ingest command."""

    @patch("doceater.cli.FileWatcher")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.Path")
    def test_ingest_command_success(self, mock_path_class, mock_get_db_manager,
                                    mock_watcher_class, cli_runner, mock_db_manager,
                                    mock_file_watcher):
        """Test successful file ingestion."""
        # Mock path
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.expanduser.return_value = mock_path
        mock_path.resolve.return_value = mock_path
        mock_path_class.return_value = mock_path
        
        mock_get_db_manager.return_value = mock_db_manager
        mock_watcher_class.return_value = mock_file_watcher
        
        result = cli_runner.invoke(app, ["ingest", "test.pdf"])
        
        assert result.exit_code == 0
        assert "Ingesting file" in result.stdout
        assert "File ingested successfully" in result.stdout
        mock_file_watcher.manual_process_file.assert_called_once_with(mock_path)

    @patch("doceater.cli.Path")
    def test_ingest_command_file_not_found(self, mock_path_class, cli_runner):
        """Test ingestion of non-existent file."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path.expanduser.return_value = mock_path
        mock_path.resolve.return_value = mock_path
        mock_path_class.return_value = mock_path
        
        result = cli_runner.invoke(app, ["ingest", "nonexistent.pdf"])
        
        assert result.exit_code == 1
        assert "File not found" in result.stdout

    @patch("doceater.cli.FileWatcher")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.Path")
    def test_ingest_command_failure(self, mock_path_class, mock_get_db_manager,
                                    mock_watcher_class, cli_runner, mock_db_manager):
        """Test failed file ingestion."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.expanduser.return_value = mock_path
        mock_path.resolve.return_value = mock_path
        mock_path_class.return_value = mock_path
        
        mock_get_db_manager.return_value = mock_db_manager
        
        mock_file_watcher = AsyncMock()
        mock_file_watcher.manual_process_file.return_value = False
        mock_watcher_class.return_value = mock_file_watcher
        
        result = cli_runner.invoke(app, ["ingest", "test.pdf"])
        
        assert result.exit_code == 1
        assert "Failed to ingest file" in result.stdout


class TestListCommand:
    """Test list command."""

    @patch("doceater.cli.get_db_manager")
    def test_list_command_basic(self, mock_get_db_manager, cli_runner, mock_db_manager):
        """Test basic list command."""
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        mock_db_manager.list_documents.assert_called_once_with(status=None, limit=20)
        mock_db_manager.close.assert_called_once()

    @patch("doceater.cli.get_db_manager")
    def test_list_command_with_status_filter(self, mock_get_db_manager, cli_runner, mock_db_manager):
        """Test list command with status filter."""
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["list", "--status", "completed"])

        assert result.exit_code == 0
        mock_db_manager.list_documents.assert_called_once_with(
            status=DocumentStatus.COMPLETED, limit=20
        )

    @patch("doceater.cli.get_db_manager")
    def test_list_command_with_limit(self, mock_get_db_manager, cli_runner, mock_db_manager):
        """Test list command with custom limit."""
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["list", "--limit", "50"])

        assert result.exit_code == 0
        mock_db_manager.list_documents.assert_called_once_with(status=None, limit=50)

    @patch("doceater.cli.get_db_manager")
    def test_list_command_invalid_status(self, mock_get_db_manager, cli_runner, mock_db_manager):
        """Test list command with invalid status."""
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["list", "--status", "invalid"])

        assert result.exit_code == 1
        assert "Invalid status" in result.stdout

    @patch("doceater.cli.get_db_manager")
    def test_list_command_no_documents(self, mock_get_db_manager, cli_runner):
        """Test list command when no documents exist."""
        mock_db_manager = AsyncMock()
        mock_db_manager.list_documents.return_value = []
        mock_db_manager.close.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No documents found" in result.stdout


class TestShowCommand:
    """Test show command."""

    @patch("doceater.cli.get_db_manager")
    def test_show_command_success(self, mock_get_db_manager, cli_runner, mock_db_manager):
        """Test successful document show."""
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["show", "12345678-1234-5678-9012-123456789012"])

        assert result.exit_code == 0
        assert "Document: test.pdf" in result.stdout
        assert "Status: completed" in result.stdout
        mock_db_manager.get_document_by_id.assert_called_once()

    @patch("doceater.cli.get_db_manager")
    def test_show_command_invalid_uuid(self, mock_get_db_manager, cli_runner, mock_db_manager):
        """Test show command with invalid UUID."""
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["show", "invalid-uuid"])

        assert result.exit_code == 1
        assert "Invalid document ID" in result.stdout

    @patch("doceater.cli.get_db_manager")
    def test_show_command_document_not_found(self, mock_get_db_manager, cli_runner):
        """Test show command for non-existent document."""
        mock_db_manager = AsyncMock()
        mock_db_manager.get_document_by_id.return_value = None
        mock_db_manager.close.return_value = None
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["show", "12345678-1234-5678-9012-123456789012"])

        assert result.exit_code == 1
        assert "Document not found" in result.stdout


class TestStatusCommand:
    """Test status command."""

    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_status_command_success(self, mock_get_settings, mock_get_db_manager,
                                    cli_runner, mock_settings, mock_db_manager):
        """Test successful status command."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "DocEater Status" in result.stdout
        assert "Watch folder" in result.stdout
        assert "Database" in result.stdout
        # Should call list_documents for each status
        assert mock_db_manager.list_documents.call_count == len(DocumentStatus)


class TestImagesCommand:
    """Test images command."""

    @patch("doceater.cli.ImageStorageManager")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_images_list_all(self, mock_get_settings, mock_get_db_manager,
                             mock_storage_class, cli_runner, mock_settings,
                             mock_db_manager, mock_image_storage):
        """Test images list command for all images."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        mock_storage_class.return_value = mock_image_storage

        result = cli_runner.invoke(app, ["images", "list"])

        assert result.exit_code == 0
        assert "Recent images" in result.stdout
        mock_db_manager.get_images_by_type.assert_called()

    @patch("doceater.cli.ImageStorageManager")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_images_list_by_document(self, mock_get_settings, mock_get_db_manager,
                                     mock_storage_class, cli_runner, mock_settings,
                                     mock_db_manager, mock_image_storage):
        """Test images list command for specific document."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        mock_storage_class.return_value = mock_image_storage

        result = cli_runner.invoke(app, [
            "images", "list",
            "--document-id", "12345678-1234-5678-9012-123456789012"
        ])

        assert result.exit_code == 0
        assert "Document: test.pdf" in result.stdout
        mock_db_manager.get_document_by_id.assert_called_once()
        mock_db_manager.get_document_images.assert_called_once()

    @patch("doceater.cli.ImageStorageManager")
    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_images_stats(self, mock_get_settings, mock_get_db_manager,
                          mock_storage_class, cli_runner, mock_settings,
                          mock_db_manager, mock_image_storage):
        """Test images stats command."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager
        mock_storage_class.return_value = mock_image_storage

        result = cli_runner.invoke(app, ["images", "stats"])

        assert result.exit_code == 0
        assert "Image Storage Statistics" in result.stdout
        assert "Total files: 10" in result.stdout
        assert "Total size: 5.50 MB" in result.stdout
        mock_image_storage.get_storage_stats.assert_called_once()

    @patch("doceater.cli.get_db_manager")
    @patch("doceater.cli.get_settings")
    def test_images_invalid_action(self, mock_get_settings, mock_get_db_manager,
                                   cli_runner, mock_settings, mock_db_manager):
        """Test images command with invalid action."""
        mock_get_settings.return_value = mock_settings
        mock_get_db_manager.return_value = mock_db_manager

        result = cli_runner.invoke(app, ["images", "invalid"])

        assert result.exit_code == 1
        assert "Unknown action" in result.stdout
