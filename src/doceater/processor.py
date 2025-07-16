"""Document processing using Docling."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

import aiofiles
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter
from loguru import logger

from .config import Settings, get_settings
from .database import DatabaseManager, get_db_manager
from .models import DocumentStatus, LogLevel


class DocumentProcessor:
    """Handles document processing using Docling."""

    def __init__(
        self,
        settings: Settings | None = None,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db_manager = db_manager or get_db_manager()
        self._converter: DocumentConverter | None = None

    @property
    def converter(self) -> DocumentConverter:
        """Get or create the Docling converter."""
        if self._converter is None:
            # Use default configuration for now to avoid compatibility issues
            self._converter = DocumentConverter()
            logger.info("Initialized Docling converter")

        return self._converter

    async def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        hash_sha256 = hashlib.sha256()

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    def get_mime_type(self, file_path: Path) -> str | None:
        """Get MIME type of a file."""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type

    def is_supported_file(self, file_path: Path) -> bool:
        """Check if file is supported for processing."""
        # Check extension
        if file_path.suffix.lower() not in self.settings.supported_extensions:
            return False

        # Check size
        try:
            file_size = file_path.stat().st_size
            if file_size > self.settings.max_file_size_bytes:
                logger.warning(f"File too large: {file_path} ({file_size} bytes)")
                return False
        except OSError:
            logger.error(f"Cannot access file: {file_path}")
            return False

        # Check exclude patterns
        filename = file_path.name
        for pattern in self.settings.exclude_patterns:
            if filename.startswith(pattern.replace("*", "")):
                return False

        return True

    async def extract_metadata(self, file_path: Path) -> dict[str, str]:
        """Extract metadata from a file."""
        try:
            stat = file_path.stat()
            metadata = {
                "file_extension": file_path.suffix.lower(),
                "file_size_bytes": str(stat.st_size),
                "created_time": str(stat.st_ctime),
                "modified_time": str(stat.st_mtime),
            }

            # Add MIME type if available
            mime_type = self.get_mime_type(file_path)
            if mime_type:
                metadata["mime_type"] = mime_type

            return metadata
        except Exception as e:
            logger.error(f"Failed to extract metadata from {file_path}: {e}")
            return {}

    async def convert_to_markdown(self, file_path: Path) -> str:
        """Convert document to Markdown using Docling."""
        try:
            logger.info(f"Converting document to Markdown: {file_path}")

            # Convert document
            result = self.converter.convert(str(file_path))

            # Extract markdown content
            markdown_content = result.document.export_to_markdown()

            logger.info(f"Successfully converted document: {file_path}")
            return markdown_content

        except Exception as e:
            logger.error(f"Failed to convert document {file_path}: {e}")
            raise

    async def process_file(self, file_path: Path) -> bool:
        """Process a single file completely."""
        try:
            # Validate file
            if not self.is_supported_file(file_path):
                logger.debug(f"Skipping unsupported file: {file_path}")
                return False

            # Check if file already exists in database
            existing_doc = await self.db_manager.get_document_by_path(str(file_path))
            if existing_doc:
                logger.debug(f"File already processed: {file_path}")
                return True

            # Calculate file hash for deduplication
            content_hash = await self.calculate_file_hash(file_path)
            existing_by_hash = await self.db_manager.get_document_by_hash(content_hash)
            if existing_by_hash:
                logger.info(f"File with same content already exists: {file_path}")
                return True

            # Create document record
            file_size = file_path.stat().st_size
            mime_type = self.get_mime_type(file_path)

            document = await self.db_manager.create_document(
                file_path=str(file_path),
                filename=file_path.name,
                content_hash=content_hash,
                file_size=file_size,
                mime_type=mime_type,
            )

            # Update status to processing
            await self.db_manager.update_document_status(
                document.id, DocumentStatus.PROCESSING
            )

            try:
                # Convert to markdown
                markdown_content = await self.convert_to_markdown(file_path)

                # Update document with content
                await self.db_manager.update_document_content(
                    document.id,
                    markdown_content,
                    DocumentStatus.COMPLETED,
                )

                # Extract and store metadata
                metadata = await self.extract_metadata(file_path)
                if metadata:
                    await self.db_manager.add_document_metadata(document.id, metadata)

                # Log success
                await self.db_manager.log_processing(
                    LogLevel.INFO,
                    f"Successfully processed file: {file_path.name}",
                    document.id,
                    {"file_size": file_size, "content_length": len(markdown_content)},
                )

                logger.info(f"Successfully processed file: {file_path}")
                return True

            except Exception as e:
                # Update status to failed
                await self.db_manager.update_document_status(
                    document.id, DocumentStatus.FAILED
                )

                # Log error with partial content recovery attempt
                error_details = {"error": str(e), "error_type": type(e).__name__}

                # Try to extract partial content
                try:
                    # For corrupted files, try to extract what we can
                    partial_content = f"# {file_path.name}\n\n*File processing failed: {e}*\n\n"
                    partial_content += f"File information:\n- Size: {file_size} bytes\n- Type: {mime_type or 'unknown'}\n"

                    await self.db_manager.update_document_content(
                        document.id,
                        partial_content,
                        DocumentStatus.FAILED,
                    )

                    error_details["partial_content_saved"] = True
                    logger.warning(f"Saved partial content for failed file: {file_path}")

                except Exception as partial_error:
                    error_details["partial_content_error"] = str(partial_error)
                    logger.error(f"Failed to save partial content: {partial_error}")

                await self.db_manager.log_processing(
                    LogLevel.ERROR,
                    f"Failed to process file: {file_path.name}",
                    document.id,
                    error_details,
                )

                logger.error(f"Failed to process file {file_path}: {e}")
                return False

        except Exception as e:
            logger.error(f"Unexpected error processing file {file_path}: {e}")
            return False
