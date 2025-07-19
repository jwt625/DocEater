"""Document processing using Docling."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

import aiofiles
from loguru import logger

from .config import Settings, get_settings
from .database import DatabaseManager, get_db_manager
from .docling_wrapper import DoclingWrapper
from .image_storage import ImageStorageManager
from .models import DocumentStatus, LogLevel


class DocumentProcessor:
    """Handles document processing using Docling."""

    def __init__(
        self,
        settings: Settings | None = None,
        db_manager: DatabaseManager | None = None,
        enable_formula_enrichment: bool = True,
        image_storage: ImageStorageManager | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db_manager = db_manager or get_db_manager()
        self.image_storage = image_storage or ImageStorageManager(self.settings)
        self._docling_wrapper: DoclingWrapper | None = None
        self.enable_formula_enrichment = enable_formula_enrichment

    @property
    def docling_wrapper(self) -> DoclingWrapper:
        """Get or create the Docling wrapper."""
        if self._docling_wrapper is None:
            self._docling_wrapper = DoclingWrapper(
                enable_formula_enrichment=self.enable_formula_enrichment,
                enable_image_extraction=self.settings.images_enabled,
            )
            logger.info("Initialized Docling wrapper with enhanced configuration")

        return self._docling_wrapper

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
        """Convert document to Markdown using Docling with enhanced configuration."""
        try:
            logger.info(f"Converting document to Markdown: {file_path}")

            # Use the wrapper to convert with enhanced configuration
            markdown_content = self.docling_wrapper.convert_to_markdown(file_path)

            logger.info(f"Successfully converted document: {file_path}")
            return markdown_content

        except Exception as e:
            logger.error(f"Failed to convert document {file_path}: {e}")
            raise

    async def convert_to_markdown_with_images(
        self, file_path: Path
    ) -> tuple[str, list[Path]]:
        """Convert document to markdown and extract images.

        Args:
            file_path: Path to the document to convert

        Returns:
            Tuple of (markdown_content, list_of_temp_image_paths)
        """
        try:
            if self.settings.images_enabled:
                # Use the enhanced method that extracts to temporary directory
                return self.docling_wrapper.convert_to_markdown_with_storage(file_path)
            else:
                # Fall back to text-only conversion
                markdown_content = await self.convert_to_markdown(file_path)
                return markdown_content, []
        except Exception as e:
            logger.error(f"Failed to convert document with images {file_path}: {e}")
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
                # Convert to markdown with optional image extraction
                if self.settings.images_enabled:
                    (
                        markdown_content,
                        temp_image_paths,
                    ) = await self.convert_to_markdown_with_images(file_path)

                    # Store images persistently
                    if temp_image_paths:
                        try:
                            stored_images = await self.image_storage.store_images(
                                document.id, temp_image_paths
                            )

                            # Save image metadata to database
                            for stored_image in stored_images:
                                try:
                                    await self.db_manager.create_document_image(
                                        document_id=document.id,
                                        image_path=str(stored_image.path),
                                        filename=stored_image.filename,
                                        image_type=stored_image.image_type,
                                        image_index=stored_image.image_index,
                                        file_size=stored_image.file_size,
                                        width=stored_image.width,
                                        height=stored_image.height,
                                        format=stored_image.format,
                                        extraction_method="docling",
                                        quality_score=None,
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Failed to save image metadata for {stored_image.filename}: {e}"
                                    )
                                    # Continue with other images

                            logger.info(
                                f"Stored {len(stored_images)} images for document {document.id}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Failed to store images for document {document.id}: {e}"
                            )
                            # Continue processing without images
                            stored_images = []

                        # Clean up temporary images
                        import shutil

                        for temp_path in temp_image_paths:
                            try:
                                if temp_path.exists():
                                    # Remove the temporary directory
                                    temp_dir = temp_path.parent
                                    if temp_dir.name.startswith("doceater_images_"):
                                        shutil.rmtree(temp_dir, ignore_errors=True)
                                    break  # Only need to remove the temp dir once
                            except Exception as e:
                                logger.warning(
                                    f"Failed to cleanup temporary image directory: {e}"
                                )
                else:
                    # Text-only conversion
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

                # Log success with image information
                log_details = {
                    "file_size": file_size,
                    "content_length": len(markdown_content),
                    "images_enabled": self.settings.images_enabled,
                }

                if self.settings.images_enabled and "stored_images" in locals():
                    log_details["images_extracted"] = len(stored_images)
                    log_details["image_types"] = [
                        img.image_type.value for img in stored_images
                    ]

                await self.db_manager.log_processing(
                    LogLevel.INFO,
                    f"Successfully processed file: {file_path.name}",
                    document.id,
                    log_details,
                )

                logger.info(f"Successfully processed file: {file_path}")
                return True

            except Exception as e:
                # Update status to failed
                await self.db_manager.update_document_status(
                    document.id, DocumentStatus.FAILED
                )

                # Cleanup any partially stored images on failure
                if self.settings.images_enabled and self.settings.images_cleanup_failed:
                    try:
                        await self.image_storage.cleanup_document_images(document.id)
                        logger.debug(
                            f"Cleaned up images for failed document {document.id}"
                        )
                    except Exception as cleanup_error:
                        logger.warning(
                            f"Failed to cleanup images for failed document: {cleanup_error}"
                        )

                # Log error with partial content recovery attempt
                error_details = {"error": str(e), "error_type": type(e).__name__}

                # Try to extract partial content
                try:
                    # For corrupted files, try to extract what we can
                    partial_content = (
                        f"# {file_path.name}\n\n*File processing failed: {e}*\n\n"
                    )
                    partial_content += f"File information:\n- Size: {file_size} bytes\n- Type: {mime_type or 'unknown'}\n"

                    await self.db_manager.update_document_content(
                        document.id,
                        partial_content,
                        DocumentStatus.FAILED,
                    )

                    error_details["partial_content_saved"] = True
                    logger.warning(
                        f"Saved partial content for failed file: {file_path}"
                    )

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
