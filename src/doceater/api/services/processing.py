"""
Document processing service for API endpoints.

This service integrates the existing DocumentProcessor and EmbeddingService
to provide background document processing for uploaded files.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from doceater.config import Settings
from doceater.database import DatabaseManager
from doceater.embeddings.service import get_embedding_service
from doceater.models import DocumentStatus, LogLevel
from doceater.processor import DocumentProcessor


class DocumentProcessingService:
    """Service for processing documents uploaded via API."""

    def __init__(self, settings: Settings):
        """Initialize the processing service."""
        self.settings = settings
        self.db_manager = DatabaseManager(settings)
        self.document_processor = DocumentProcessor(settings)
        self.embedding_service = get_embedding_service()
        self._processing_tasks: set[asyncio.Task] = set()

    async def process_document_async(
        self, document_id: uuid.UUID, file_path: Path
    ) -> None:
        """
        Process a document asynchronously in the background.

        This method:
        1. Uses DocumentProcessor to extract content and images
        2. Generates text and image embeddings using EmbeddingService
        3. Updates document status and metadata

        Args:
            document_id: UUID of the document to process
            file_path: Path to the uploaded file
        """
        try:
            logger.info(f"Starting background processing for document {document_id}")

            # Update status to processing
            await self.db_manager.update_document_status(
                document_id, DocumentStatus.PROCESSING
            )

            # Step 1: Process document with existing DocumentProcessor
            # This extracts content, images, and stores them in the database
            # Pass the existing document_id to avoid duplicate creation
            success = await self.document_processor.process_file(file_path, document_id)

            if not success:
                logger.error(f"Document processing failed for {document_id}")
                await self.db_manager.update_document_status(
                    document_id, DocumentStatus.FAILED
                )
                return

            # Step 2: Generate embeddings for the processed content
            logger.info(f"Starting embedding generation for document {document_id}")
            await self._generate_embeddings(document_id)
            logger.info(f"Completed embedding generation for document {document_id}")

            # Step 3: Update final status
            await self.db_manager.update_document_status(
                document_id, DocumentStatus.COMPLETED
            )

            logger.info(f"✅ Successfully processed document {document_id}")

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")

            # Log the error to the processing logs table for debugging
            await self.db_manager.log_processing(
                LogLevel.ERROR,
                f"Document processing failed: {str(e)}",
                document_id,
                {"error": str(e), "error_type": type(e).__name__},
            )

            await self.db_manager.update_document_status(
                document_id, DocumentStatus.FAILED
            )
            raise
        finally:
            # Clean up temporary file
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.debug(f"Cleaned up temporary file: {file_path}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to clean up temporary file {file_path}: {cleanup_error}"
                    )

    async def _generate_embeddings(self, document_id: uuid.UUID) -> None:
        """Generate text and image embeddings for a processed document."""
        try:
            # Get the document to access its content
            document = await self.db_manager.get_document_by_id(document_id)
            if not document or not document.markdown_content:
                logger.warning(f"No content found for document {document_id}")
                return

            # Generate text embeddings
            await self._generate_text_embeddings(document_id, document.markdown_content)

            # Generate image embeddings if images were extracted
            await self._generate_image_embeddings(document_id)

        except Exception as e:
            logger.error(f"Error generating embeddings for document {document_id}: {e}")
            raise

    async def _generate_text_embeddings(
        self, document_id: uuid.UUID, content: str
    ) -> None:
        """Generate and store text embeddings for document content."""
        try:
            # Simple chunking strategy - split by paragraphs
            # TODO: Implement more sophisticated chunking
            chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]

            if not chunks:
                logger.warning(f"No text chunks found for document {document_id}")
                return

            # Generate embeddings for all chunks
            embeddings = await self.embedding_service.generate_text_embeddings(chunks)

            # Store embeddings in database
            for i, (chunk, embedding) in enumerate(
                zip(chunks, embeddings, strict=False)
            ):
                await self.db_manager.create_text_embedding(
                    document_id=document_id,
                    chunk_text=chunk,
                    embedding=embedding,
                    chunk_index=i,
                    page_number=None,  # TODO: Extract page info from content
                    bbox_coordinates=None,
                    token_count=len(chunk.split()),  # Simple token count
                )

            logger.info(
                f"Generated {len(embeddings)} text embeddings for document {document_id}"
            )

        except Exception as e:
            logger.error(
                f"Error generating text embeddings for document {document_id}: {e}"
            )
            raise

    async def _generate_image_embeddings(self, document_id: uuid.UUID) -> None:
        """Generate and store image embeddings for extracted images."""
        try:
            # Get all images for this document
            images = await self.db_manager.get_document_images(document_id)

            if not images:
                logger.debug(f"No images found for document {document_id}")
                return

            # Load images and generate embeddings
            from PIL import Image

            from doceater.image_storage import ImageStorageManager

            image_storage = ImageStorageManager(self.settings)
            pil_images = []
            image_records = []

            for image_record in images:
                try:
                    # Get full image path
                    image_path = await image_storage.get_image_path(
                        document_id, image_record.image_path
                    )

                    # Load image
                    pil_image = Image.open(image_path)
                    pil_images.append(pil_image)
                    image_records.append(image_record)

                except Exception as e:
                    logger.warning(
                        f"Failed to load image {image_record.image_path}: {e}"
                    )
                    continue

            if not pil_images:
                logger.warning(f"No valid images found for document {document_id}")
                return

            # Generate embeddings for all images
            embeddings = await self.embedding_service.generate_image_embeddings(
                pil_images
            )

            # Store embeddings in database
            for image_record, embedding in zip(image_records, embeddings, strict=False):
                await self.db_manager.create_image_embedding(
                    document_image_id=image_record.id,
                    embedding=embedding,
                    description=None,  # TODO: Generate image descriptions
                    ocr_text=None,  # TODO: Extract OCR text
                )

            logger.info(
                f"Generated {len(embeddings)} image embeddings for document {document_id}"
            )

        except Exception as e:
            logger.error(
                f"Error generating image embeddings for document {document_id}: {e}"
            )
            raise

    def start_background_processing(
        self, document_id: uuid.UUID, file_path: Path
    ) -> None:
        """
        Start background processing for a document.

        This creates an asyncio task that runs in the background without blocking
        the API response.
        """
        task = asyncio.create_task(self.process_document_async(document_id, file_path))

        # Add task to set to prevent garbage collection
        self._processing_tasks.add(task)

        # Remove task from set when it completes
        task.add_done_callback(self._processing_tasks.discard)

        logger.info(f"Started background processing task for document {document_id}")

    async def get_processing_status(self) -> dict[str, Any]:
        """Get current processing status and statistics."""
        active_tasks = len(self._processing_tasks)

        # Get database statistics
        stats = await self.db_manager.get_stats()

        return {
            "active_processing_tasks": active_tasks,
            "embedding_model_loaded": self.embedding_service.is_model_loaded,
            **stats,
        }

    async def cleanup(self) -> None:
        """Cleanup resources and cancel pending tasks."""
        if self._processing_tasks:
            logger.info(
                f"Cancelling {len(self._processing_tasks)} pending processing tasks"
            )
            for task in self._processing_tasks:
                task.cancel()

            # Wait for tasks to complete cancellation
            await asyncio.gather(*self._processing_tasks, return_exceptions=True)
            self._processing_tasks.clear()
