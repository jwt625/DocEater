"""File system watcher for DocEater."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import Settings, get_settings
from .processor import DocumentProcessor


class FileEventHandler(FileSystemEventHandler):
    """Handles file system events."""

    def __init__(self, processor: DocumentProcessor, settings: Settings) -> None:
        super().__init__()
        self.processor = processor
        self.settings = settings
        self.processing_queue: asyncio.Queue[Path] = asyncio.Queue()
        self._debounce_tasks: dict[str, asyncio.Task[Any]] = {}

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            self._queue_file_for_processing(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            self._queue_file_for_processing(Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events."""
        if not event.is_directory and hasattr(event, 'dest_path'):
            self._queue_file_for_processing(Path(event.dest_path))

    def _queue_file_for_processing(self, file_path: Path) -> None:
        """Queue a file for processing with debouncing."""
        file_key = str(file_path)

        # Cancel existing debounce task for this file
        if file_key in self._debounce_tasks:
            self._debounce_tasks[file_key].cancel()

        # Create new debounce task
        async def debounced_add() -> None:
            await asyncio.sleep(self.settings.processing_delay_seconds)
            try:
                await self.processing_queue.put(file_path)
                logger.debug(f"Queued file for processing: {file_path}")
            except Exception as e:
                logger.error(f"Failed to queue file {file_path}: {e}")
            finally:
                self._debounce_tasks.pop(file_key, None)

        self._debounce_tasks[file_key] = asyncio.create_task(debounced_add())


class FileWatcher:
    """Watches a folder for new files and processes them."""

    def __init__(
        self,
        settings: Settings | None = None,
        processor: DocumentProcessor | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.processor = processor or DocumentProcessor(self.settings)
        self.observer: Observer | None = None
        self.event_handler: FileEventHandler | None = None
        self._processing_tasks: set[asyncio.Task[Any]] = set()
        self._running = False

    async def start_watching(self) -> None:
        """Start watching the configured folder."""
        if self._running:
            logger.warning("File watcher is already running")
            return

        watch_path = Path(self.settings.watch_folder)
        if not watch_path.exists():
            logger.error(f"Watch folder does not exist: {watch_path}")
            return

        logger.info(f"Starting file watcher for: {watch_path}")

        # Create event handler
        self.event_handler = FileEventHandler(self.processor, self.settings)

        # Set up observer
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(watch_path),
            recursive=self.settings.watch_recursive,
        )

        # Start observer
        self.observer.start()
        self._running = True

        # Start processing queue consumer
        asyncio.create_task(self._process_queue())

        logger.info("File watcher started successfully")

    async def stop_watching(self) -> None:
        """Stop watching and clean up."""
        if not self._running:
            return

        logger.info("Stopping file watcher...")

        self._running = False

        # Stop observer
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        # Cancel all processing tasks
        for task in self._processing_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._processing_tasks:
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)
            self._processing_tasks.clear()

        logger.info("File watcher stopped")

    async def _process_queue(self) -> None:
        """Process files from the queue."""
        if not self.event_handler:
            return

        logger.info("Started processing queue consumer")

        while self._running:
            try:
                # Wait for a file to process (with timeout to check if still running)
                try:
                    file_path = await asyncio.wait_for(
                        self.event_handler.processing_queue.get(),
                        timeout=1.0
                    )
                except TimeoutError:
                    continue

                # Check if we have too many concurrent tasks
                if len(self._processing_tasks) >= self.settings.max_concurrent_files:
                    # Wait for at least one task to complete
                    done, pending = await asyncio.wait(
                        self._processing_tasks,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    self._processing_tasks = pending

                # Create processing task
                task = asyncio.create_task(self._process_file_safe(file_path))
                self._processing_tasks.add(task)

                # Clean up completed tasks
                self._processing_tasks = {t for t in self._processing_tasks if not t.done()}

            except Exception as e:
                logger.error(f"Error in processing queue: {e}")
                await asyncio.sleep(1)

        logger.info("Processing queue consumer stopped")

    async def _process_file_safe(self, file_path: Path) -> None:
        """Process a file with error handling."""
        try:
            await self.processor.process_file(file_path)
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

    async def process_existing_files(self) -> None:
        """Process existing files in the watch folder."""
        watch_path = Path(self.settings.watch_folder)
        if not watch_path.exists():
            logger.error(f"Watch folder does not exist: {watch_path}")
            return

        logger.info(f"Processing existing files in: {watch_path}")

        # Find all supported files
        files_to_process = []
        for ext in self.settings.supported_extensions:
            if self.settings.watch_recursive:
                pattern = f"**/*{ext}"
            else:
                pattern = f"*{ext}"

            files_to_process.extend(watch_path.glob(pattern))

        logger.info(f"Found {len(files_to_process)} existing files to process")

        # Process files with concurrency limit
        semaphore = asyncio.Semaphore(self.settings.max_concurrent_files)

        async def process_with_semaphore(file_path: Path) -> None:
            async with semaphore:
                await self.processor.process_file(file_path)

        # Process all files
        tasks = [process_with_semaphore(file_path) for file_path in files_to_process]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Finished processing existing files")

    async def manual_process_file(self, file_path: str | Path) -> bool:
        """Manually process a specific file."""
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False

        logger.info(f"Manually processing file: {file_path}")
        return await self.processor.process_file(file_path)
