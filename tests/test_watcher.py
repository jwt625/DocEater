"""Tests for file watcher functionality."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent

from doceater.processor import DocumentProcessor
from doceater.watcher import FileEventHandler, FileWatcher


class TestFileEventHandler:
    """Test the FileEventHandler class."""

    @pytest.fixture
    def mock_processor(self) -> AsyncMock:
        """Create a mock document processor."""
        processor = AsyncMock(spec=DocumentProcessor)
        processor.process_file = AsyncMock(return_value=True)
        return processor

    @pytest.fixture
    def event_handler(
        self, mock_processor: AsyncMock, test_settings
    ) -> FileEventHandler:
        """Create a FileEventHandler instance for testing."""
        return FileEventHandler(mock_processor, test_settings)

    def test_handler_initialization(
        self, event_handler: FileEventHandler, mock_processor: AsyncMock, test_settings
    ):
        """Test FileEventHandler initialization."""
        assert event_handler.processor is mock_processor
        assert event_handler.settings is test_settings
        assert isinstance(event_handler.processing_queue, asyncio.Queue)
        assert isinstance(event_handler._debounce_tasks, dict)
        assert len(event_handler._debounce_tasks) == 0

    @pytest.mark.asyncio
    async def test_on_created_file(
        self, event_handler: FileEventHandler, temp_dir: Path
    ):
        """Test handling file creation events."""
        test_file = temp_dir / "test.pdf"
        test_file.touch()

        event = FileCreatedEvent(str(test_file))
        event_handler.on_created(event)

        # Should have created a debounce task
        assert len(event_handler._debounce_tasks) == 1
        assert str(test_file) in event_handler._debounce_tasks

    def test_on_created_directory_ignored(
        self, event_handler: FileEventHandler, temp_dir: Path
    ):
        """Test that directory creation events are ignored."""
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()

        event = FileCreatedEvent(str(test_dir))
        event.is_directory = True
        event_handler.on_created(event)

        # Should not create any debounce tasks
        assert len(event_handler._debounce_tasks) == 0

    @pytest.mark.asyncio
    async def test_on_modified_file(
        self, event_handler: FileEventHandler, temp_dir: Path
    ):
        """Test handling file modification events."""
        test_file = temp_dir / "test.pdf"
        test_file.write_text("content")

        event = FileModifiedEvent(str(test_file))
        event_handler.on_modified(event)

        # Should have created a debounce task
        assert len(event_handler._debounce_tasks) == 1
        assert str(test_file) in event_handler._debounce_tasks

    @pytest.mark.asyncio
    async def test_on_moved_file(self, event_handler: FileEventHandler, temp_dir: Path):
        """Test handling file move events."""
        source_file = temp_dir / "source.pdf"
        dest_file = temp_dir / "dest.pdf"
        source_file.touch()

        event = FileMovedEvent(str(source_file), str(dest_file))
        event_handler.on_moved(event)

        # Should have created a debounce task for destination
        assert len(event_handler._debounce_tasks) == 1
        assert str(dest_file) in event_handler._debounce_tasks

    @pytest.mark.asyncio
    async def test_debounce_cancellation(
        self, event_handler: FileEventHandler, temp_dir: Path
    ):
        """Test that rapid file events are debounced properly."""
        test_file = temp_dir / "test.pdf"
        test_file.touch()

        # Create first event
        event1 = FileCreatedEvent(str(test_file))
        event_handler.on_created(event1)

        first_task = event_handler._debounce_tasks[str(test_file)]
        assert not first_task.cancelled()

        # Create second event for same file (should cancel first)
        event2 = FileModifiedEvent(str(test_file))
        event_handler.on_modified(event2)

        # Wait a moment for cancellation to take effect
        await asyncio.sleep(0.01)

        # First task should be cancelled, second should be active
        assert first_task.cancelled()
        assert len(event_handler._debounce_tasks) == 1

        second_task = event_handler._debounce_tasks[str(test_file)]
        assert not second_task.cancelled()
        assert second_task is not first_task

    @pytest.mark.asyncio
    async def test_queue_file_processing(
        self, event_handler: FileEventHandler, temp_dir: Path
    ):
        """Test that files are queued for processing after debounce delay."""
        test_file = temp_dir / "test.pdf"
        test_file.touch()

        event = FileCreatedEvent(str(test_file))
        event_handler.on_created(event)

        # Wait for debounce delay plus a bit more
        await asyncio.sleep(event_handler.settings.processing_delay_seconds + 0.05)

        # File should be in queue
        assert not event_handler.processing_queue.empty()
        queued_file = await event_handler.processing_queue.get()
        assert queued_file == test_file

        # Debounce task should be cleaned up
        assert len(event_handler._debounce_tasks) == 0


class TestFileWatcher:
    """Test the FileWatcher class."""

    @pytest.fixture
    def mock_processor(self) -> AsyncMock:
        """Create a mock document processor."""
        processor = AsyncMock(spec=DocumentProcessor)
        processor.process_file = AsyncMock(return_value=True)
        return processor

    @pytest.fixture
    def file_watcher(self, test_settings, mock_processor: AsyncMock) -> FileWatcher:
        """Create a FileWatcher instance for testing."""
        return FileWatcher(test_settings, mock_processor)

    def test_watcher_initialization(
        self, file_watcher: FileWatcher, test_settings, mock_processor: AsyncMock
    ):
        """Test FileWatcher initialization."""
        assert file_watcher.settings is test_settings
        assert file_watcher.processor is mock_processor
        assert file_watcher.observer is None
        assert file_watcher.event_handler is None
        assert len(file_watcher._processing_tasks) == 0
        assert file_watcher._running is False

    def test_watcher_initialization_with_defaults(self, temp_dir: Path):
        """Test FileWatcher initialization with default parameters."""
        from doceater.config import Settings

        settings = Settings(watch_folder=str(temp_dir))
        watcher = FileWatcher(settings)

        assert watcher.settings is settings
        assert isinstance(watcher.processor, DocumentProcessor)

    @pytest.mark.asyncio
    async def test_start_watching_nonexistent_folder(self, test_settings):
        """Test starting watcher with non-existent folder."""
        test_settings.watch_folder = "/nonexistent/folder"
        watcher = FileWatcher(test_settings)

        await watcher.start_watching()

        # Should not start watching
        assert watcher._running is False
        assert watcher.observer is None

    @pytest.mark.asyncio
    async def test_start_watching_already_running(self, file_watcher: FileWatcher):
        """Test starting watcher when already running."""
        file_watcher._running = True

        with patch("doceater.watcher.logger") as mock_logger:
            await file_watcher.start_watching()
            mock_logger.warning.assert_called_once_with(
                "File watcher is already running"
            )

    @pytest.mark.asyncio
    async def test_start_watching_success(self, file_watcher: FileWatcher):
        """Test successful watcher startup."""
        with patch("doceater.watcher.Observer") as mock_observer_class:
            mock_observer = MagicMock()
            mock_observer_class.return_value = mock_observer

            try:
                await file_watcher.start_watching()

                # Verify watcher state
                assert file_watcher._running is True
                assert file_watcher.observer is mock_observer
                assert file_watcher.event_handler is not None

                # Verify observer setup
                mock_observer.schedule.assert_called_once()
                mock_observer.start.assert_called_once()
            finally:
                # Clean up to prevent warnings
                await file_watcher.stop_watching()

    @pytest.mark.asyncio
    async def test_stop_watching_not_running(self, file_watcher: FileWatcher):
        """Test stopping watcher when not running."""
        await file_watcher.stop_watching()
        # Should complete without error
        assert file_watcher._running is False

    @pytest.mark.asyncio
    async def test_stop_watching_success(self, file_watcher: FileWatcher):
        """Test successful watcher shutdown."""
        # Set up running state
        mock_observer = MagicMock()
        mock_task = asyncio.create_task(asyncio.sleep(10))  # Create real task

        file_watcher._running = True
        file_watcher.observer = mock_observer
        file_watcher._processing_tasks.add(mock_task)

        await file_watcher.stop_watching()

        # Verify cleanup
        assert file_watcher._running is False
        assert file_watcher.observer is None
        assert len(file_watcher._processing_tasks) == 0

        # Verify observer shutdown
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

        # Verify task was cancelled
        assert mock_task.cancelled()

    @pytest.mark.asyncio
    async def test_manual_process_file_success(
        self, file_watcher: FileWatcher, temp_dir: Path
    ):
        """Test manual file processing."""
        test_file = temp_dir / "test.pdf"
        test_file.write_bytes(b"test content")

        result = await file_watcher.manual_process_file(test_file)

        assert result is True
        file_watcher.processor.process_file.assert_called_once_with(test_file)

    @pytest.mark.asyncio
    async def test_manual_process_file_nonexistent(
        self, file_watcher: FileWatcher, temp_dir: Path
    ):
        """Test manual processing of non-existent file."""
        nonexistent_file = temp_dir / "nonexistent.pdf"

        result = await file_watcher.manual_process_file(nonexistent_file)

        assert result is False
        file_watcher.processor.process_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_process_file_string_path(
        self, file_watcher: FileWatcher, temp_dir: Path
    ):
        """Test manual file processing with string path."""
        test_file = temp_dir / "test.pdf"
        test_file.write_bytes(b"test content")

        result = await file_watcher.manual_process_file(str(test_file))

        assert result is True
        file_watcher.processor.process_file.assert_called_once_with(test_file)

    @pytest.mark.asyncio
    async def test_process_existing_files_empty_folder(self, file_watcher: FileWatcher):
        """Test processing existing files in empty folder."""
        await file_watcher.process_existing_files()

        # Should complete without processing any files
        file_watcher.processor.process_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_existing_files_with_files(
        self, file_watcher: FileWatcher, temp_dir: Path
    ):
        """Test processing existing files."""
        # Create test files
        pdf_file = temp_dir / "test.pdf"
        txt_file = temp_dir / "test.txt"
        ignored_file = temp_dir / "test.doc"  # Not in supported extensions

        pdf_file.write_bytes(b"pdf content")
        txt_file.write_text("text content")
        ignored_file.write_text("ignored content")

        await file_watcher.process_existing_files()

        # Should process supported files only
        assert file_watcher.processor.process_file.call_count == 2
        processed_files = {
            call.args[0].resolve()
            for call in file_watcher.processor.process_file.call_args_list
        }
        assert pdf_file.resolve() in processed_files
        assert txt_file.resolve() in processed_files
        assert ignored_file.resolve() not in processed_files

    @pytest.mark.asyncio
    async def test_process_existing_files_recursive(
        self, file_watcher: FileWatcher, temp_dir: Path
    ):
        """Test processing existing files recursively."""
        # Create nested structure
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        root_file = temp_dir / "root.pdf"
        nested_file = subdir / "nested.pdf"

        root_file.write_bytes(b"root content")
        nested_file.write_bytes(b"nested content")

        await file_watcher.process_existing_files()

        # Should process both files (recursive is True in test_settings)
        assert file_watcher.processor.process_file.call_count == 2
        processed_files = {
            call.args[0].resolve()
            for call in file_watcher.processor.process_file.call_args_list
        }
        assert root_file.resolve() in processed_files
        assert nested_file.resolve() in processed_files

    @pytest.mark.asyncio
    async def test_process_existing_files_nonexistent_folder(self, test_settings):
        """Test processing existing files with non-existent folder."""
        test_settings.watch_folder = "/nonexistent/folder"
        mock_processor = AsyncMock()
        watcher = FileWatcher(test_settings, mock_processor)

        await watcher.process_existing_files()

        # Should complete without error
        mock_processor.process_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_queue_concurrency_limit(
        self, file_watcher: FileWatcher, temp_dir: Path
    ):
        """Test that processing queue respects concurrency limits."""
        # Set low concurrency limit for testing
        file_watcher.settings.max_concurrent_files = 1

        # Create test files
        files = []
        for i in range(3):
            test_file = temp_dir / f"test_{i}.pdf"
            test_file.write_bytes(b"content")
            files.append(test_file)

        # Mock processor to simulate slow processing
        slow_processor = AsyncMock()
        processing_started = asyncio.Event()
        processing_continue = asyncio.Event()

        async def slow_process(file_path: Path) -> bool:
            processing_started.set()
            await processing_continue.wait()
            return True

        slow_processor.process_file = slow_process
        file_watcher.processor = slow_processor

        # Start watcher and queue files
        file_watcher._running = True
        file_watcher.event_handler = FileEventHandler(
            slow_processor, file_watcher.settings
        )

        # Queue all files
        for file_path in files:
            await file_watcher.event_handler.processing_queue.put(file_path)

        # Start processing queue
        queue_task = asyncio.create_task(file_watcher._process_queue())

        # Wait for first file to start processing
        await processing_started.wait()

        # Should have exactly 1 processing task (due to concurrency limit)
        assert len(file_watcher._processing_tasks) == 1

        # Allow processing to continue and stop
        processing_continue.set()
        file_watcher._running = False

        await queue_task

    @pytest.mark.asyncio
    async def test_process_file_safe_error_handling(
        self, file_watcher: FileWatcher, temp_dir: Path
    ):
        """Test that _process_file_safe handles errors gracefully."""
        test_file = temp_dir / "test.pdf"
        test_file.write_bytes(b"content")

        # Mock processor to raise exception
        file_watcher.processor.process_file = AsyncMock(
            side_effect=Exception("Processing error")
        )

        # Should not raise exception
        await file_watcher._process_file_safe(test_file)

        # Processor should have been called
        file_watcher.processor.process_file.assert_called_once_with(test_file)


class TestFileWatcherIntegration:
    """Integration tests for file watcher with real file operations."""

    @pytest.mark.asyncio
    async def test_end_to_end_file_processing(
        self, test_settings, test_db_manager, temp_dir: Path
    ):
        """Test end-to-end file processing workflow."""
        # Disable images for simpler testing
        test_settings.images_enabled = False

        # Create a real processor (but mock the docling wrapper)
        with patch("doceater.processor.DoclingWrapper") as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper.convert_to_markdown.return_value = "# Test Document\n\nContent"
            mock_wrapper_class.return_value = mock_wrapper

            processor = DocumentProcessor(test_settings, test_db_manager)
            watcher = FileWatcher(test_settings, processor)

            # Create test file
            test_file = temp_dir / "integration_test.pdf"
            test_file.write_bytes(b"test pdf content")

            # Process file manually
            result = await watcher.manual_process_file(test_file)

            # Should succeed
            assert result is True

    @pytest.mark.asyncio
    async def test_watcher_lifecycle(self, test_settings, temp_dir: Path):
        """Test complete watcher lifecycle: start, process, stop."""
        # Mock processor for faster testing
        mock_processor = AsyncMock()
        mock_processor.process_file = AsyncMock(return_value=True)

        watcher = FileWatcher(test_settings, mock_processor)

        try:
            # Start watcher
            with patch("doceater.watcher.Observer") as mock_observer_class:
                mock_observer = MagicMock()
                mock_observer_class.return_value = mock_observer

                await watcher.start_watching()

                assert watcher._running is True
                assert watcher.observer is mock_observer

                # Simulate file event
                test_file = temp_dir / "lifecycle_test.pdf"
                test_file.write_bytes(b"content")

                # Queue file directly (simulating file system event)
                await watcher.event_handler.processing_queue.put(test_file)

                # Give processing queue a moment to work
                await asyncio.sleep(0.1)

        finally:
            # Stop watcher
            await watcher.stop_watching()

            assert watcher._running is False
            assert watcher.observer is None

    @pytest.mark.asyncio
    async def test_multiple_file_events_debouncing(self, test_settings, temp_dir: Path):
        """Test that multiple rapid events for same file are properly debounced."""
        mock_processor = AsyncMock()
        mock_processor.process_file = AsyncMock(return_value=True)

        watcher = FileWatcher(test_settings, mock_processor)
        handler = FileEventHandler(mock_processor, test_settings)

        test_file = temp_dir / "debounce_test.pdf"
        test_file.write_bytes(b"initial content")

        # Simulate rapid file events
        from watchdog.events import FileCreatedEvent, FileModifiedEvent

        events = [
            FileCreatedEvent(str(test_file)),
            FileModifiedEvent(str(test_file)),
            FileModifiedEvent(str(test_file)),
            FileModifiedEvent(str(test_file)),
        ]

        # Fire all events rapidly
        for event in events:
            if hasattr(event, "is_directory"):
                event.is_directory = False
            if isinstance(event, FileCreatedEvent):
                handler.on_created(event)
            else:
                handler.on_modified(event)

        # Should have only one debounce task
        assert len(handler._debounce_tasks) == 1

        # Wait for debounce delay
        await asyncio.sleep(test_settings.processing_delay_seconds + 0.05)

        # Should have exactly one file in queue
        queued_files = []
        while not handler.processing_queue.empty():
            queued_files.append(await handler.processing_queue.get())

        assert len(queued_files) == 1
        assert queued_files[0] == test_file
