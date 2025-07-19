"""Image storage management for DocEater."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image

from .config import Settings, get_settings
from .models import ImageType


class StoredImage:
    """Represents a stored image with metadata."""

    def __init__(
        self,
        path: Path,
        filename: str,
        image_type: ImageType,
        image_index: int,
        file_size: int,
        width: int | None = None,
        height: int | None = None,
        format: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.filename = filename
        self.image_type = image_type
        self.image_index = image_index
        self.file_size = file_size
        self.width = width
        self.height = height
        self.format = format
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"<StoredImage(path={self.path}, type={self.image_type}, size={self.file_size})>"


class ImageStorageManager:
    """Manages image storage with file organization and metadata extraction."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_path = Path(self.settings.images_base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_storage_path(self, document_id: uuid.UUID) -> Path:
        """Get the storage path for a document's images."""
        if self.settings.images_organize_by_date:
            # Date-based organization: YYYY/MM/DD/document_id/
            now = datetime.now()
            date_path = self.base_path / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
        else:
            # Simple organization: document_id/
            date_path = self.base_path

        storage_path = date_path / str(document_id)
        storage_path.mkdir(parents=True, exist_ok=True)
        return storage_path

    def _extract_image_metadata(self, image_path: Path) -> dict[str, Any]:
        """Extract metadata from an image file."""
        try:
            with Image.open(image_path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                }
        except Exception as e:
            logger.warning(f"Failed to extract metadata from {image_path}: {e}")
            return {}

    def _validate_image_size(self, file_path: Path) -> bool:
        """Validate that image size is within limits."""
        file_size = file_path.stat().st_size
        max_size = self.settings.images_max_size_bytes

        if file_size > max_size:
            logger.warning(f"Image {file_path} size {file_size} exceeds limit {max_size}")
            return False

        return True

    def _determine_image_type(self, filename: str) -> ImageType:
        """Determine image type from filename."""
        filename_lower = filename.lower()

        if "table" in filename_lower:
            return ImageType.TABLE
        elif "picture" in filename_lower:
            return ImageType.PICTURE
        elif "formula" in filename_lower or "equation" in filename_lower:
            return ImageType.FORMULA
        elif "chart" in filename_lower:
            return ImageType.CHART
        elif "diagram" in filename_lower:
            return ImageType.DIAGRAM
        elif "page" in filename_lower:
            return ImageType.PAGE
        else:
            # Default to picture for unknown types
            return ImageType.PICTURE

    async def store_images(
        self, document_id: uuid.UUID, image_paths: list[Path]
    ) -> list[StoredImage]:
        """Store images for a document and return stored image information."""
        if not self.settings.images_enabled:
            logger.debug("Image storage is disabled")
            return []

        if not image_paths:
            logger.debug("No images to store")
            return []

        storage_path = self._get_storage_path(document_id)
        stored_images = []

        logger.info(f"Storing {len(image_paths)} images for document {document_id} in {storage_path}")

        for index, source_path in enumerate(image_paths, 1):
            try:
                # Validate image size
                if not self._validate_image_size(source_path):
                    continue

                # Determine image type and create target filename
                image_type = self._determine_image_type(source_path.name)
                target_filename = source_path.name
                target_path = storage_path / target_filename

                # Copy the image file
                shutil.copy2(source_path, target_path)

                # Extract metadata
                metadata = self._extract_image_metadata(target_path)
                file_size = target_path.stat().st_size

                # Create relative path from base directory
                relative_path = target_path.relative_to(self.base_path)

                # Create stored image object
                stored_image = StoredImage(
                    path=relative_path,
                    filename=target_filename,
                    image_type=image_type,
                    image_index=index,
                    file_size=file_size,
                    width=metadata.get("width"),
                    height=metadata.get("height"),
                    format=metadata.get("format"),
                    metadata=metadata,
                )

                stored_images.append(stored_image)
                logger.debug(f"Stored image: {target_path}")

            except Exception as e:
                logger.error(f"Failed to store image {source_path}: {e}")
                if self.settings.images_cleanup_failed:
                    # Try to clean up partial file
                    try:
                        if target_path.exists():
                            target_path.unlink()
                    except Exception:
                        pass
                continue

        logger.info(f"Successfully stored {len(stored_images)} images for document {document_id}")
        return stored_images

    async def get_image_path(self, document_id: uuid.UUID, relative_path: str) -> Path:
        """Get the full path to an image file."""
        return self.base_path / relative_path

    async def cleanup_document_images(self, document_id: uuid.UUID) -> int:
        """Clean up all images for a document. Returns count of deleted files."""
        storage_path = self._get_storage_path(document_id)

        if not storage_path.exists():
            return 0

        deleted_count = 0
        try:
            for image_file in storage_path.iterdir():
                if image_file.is_file():
                    image_file.unlink()
                    deleted_count += 1

            # Remove the directory if empty
            if not any(storage_path.iterdir()):
                storage_path.rmdir()

            logger.info(f"Cleaned up {deleted_count} images for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup images for document {document_id}: {e}")

        return deleted_count

    def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        total_size = 0
        total_files = 0

        for file_path in self.base_path.rglob("*"):
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size

        return {
            "base_path": str(self.base_path),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }
