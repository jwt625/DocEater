"""Tests for image storage functionality."""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from doceater.config import Settings
from doceater.image_storage import ImageStorageManager, StoredImage
from doceater.models import ImageType


class TestImageStorageManager:
    """Test cases for ImageStorageManager."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for image storage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def test_settings(self, temp_storage_dir):
        """Create test settings with temporary storage directory."""
        return Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            images_base_path=str(temp_storage_dir),
            images_enabled=True,
            images_max_size_mb=10,
        )

    @pytest.fixture
    def storage_manager(self, test_settings):
        """Create ImageStorageManager instance."""
        return ImageStorageManager(test_settings)

    @pytest.fixture
    def sample_image(self, temp_storage_dir):
        """Create a sample test image."""
        image_path = temp_storage_dir / "test_image.png"
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(image_path, 'PNG')
        
        return image_path

    def test_storage_manager_initialization(self, storage_manager, test_settings):
        """Test ImageStorageManager initialization."""
        assert storage_manager.settings == test_settings
        assert storage_manager.base_path.exists()
        assert storage_manager.base_path.is_dir()

    def test_get_storage_path_with_date_organization(self, storage_manager):
        """Test storage path generation with date organization."""
        doc_id = uuid.uuid4()
        
        with patch('doceater.image_storage.datetime') as mock_datetime:
            # Mock current date
            mock_datetime.now.return_value.year = 2025
            mock_datetime.now.return_value.month = 1
            mock_datetime.now.return_value.day = 19
            
            path = storage_manager._get_storage_path(doc_id)
            
            expected_path = storage_manager.base_path / "2025" / "01" / "19" / str(doc_id)
            assert path == expected_path
            assert path.exists()

    def test_get_storage_path_without_date_organization(self, test_settings, temp_storage_dir):
        """Test storage path generation without date organization."""
        test_settings.images_organize_by_date = False
        storage_manager = ImageStorageManager(test_settings)
        
        doc_id = uuid.uuid4()
        path = storage_manager._get_storage_path(doc_id)
        
        expected_path = storage_manager.base_path / str(doc_id)
        assert path == expected_path
        assert path.exists()

    def test_extract_image_metadata(self, storage_manager, sample_image):
        """Test image metadata extraction."""
        metadata = storage_manager._extract_image_metadata(sample_image)
        
        assert metadata['width'] == 100
        assert metadata['height'] == 100
        assert metadata['format'] == 'PNG'
        assert metadata['mode'] == 'RGB'

    def test_determine_image_type(self, storage_manager):
        """Test image type determination from filename."""
        assert storage_manager._determine_image_type("table-1.png") == ImageType.TABLE
        assert storage_manager._determine_image_type("picture-1.png") == ImageType.PICTURE
        assert storage_manager._determine_image_type("formula-1.png") == ImageType.FORMULA
        assert storage_manager._determine_image_type("chart-1.png") == ImageType.CHART
        assert storage_manager._determine_image_type("diagram-1.png") == ImageType.DIAGRAM
        assert storage_manager._determine_image_type("page-1.png") == ImageType.PAGE
        assert storage_manager._determine_image_type("unknown.png") == ImageType.PICTURE

    def test_validate_image_size(self, storage_manager, sample_image):
        """Test image size validation."""
        # Should pass for normal sized image
        assert storage_manager._validate_image_size(sample_image) is True

        # Test with size limit - check actual file size first
        file_size_bytes = sample_image.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Set limit smaller than actual file size
        storage_manager.settings.images_max_size_mb = file_size_mb * 0.5
        assert storage_manager._validate_image_size(sample_image) is False

    @pytest.mark.asyncio
    async def test_store_images_success(self, storage_manager, sample_image):
        """Test successful image storage."""
        doc_id = uuid.uuid4()
        image_paths = [sample_image]
        
        stored_images = await storage_manager.store_images(doc_id, image_paths)
        
        assert len(stored_images) == 1
        stored_image = stored_images[0]
        
        assert isinstance(stored_image, StoredImage)
        assert stored_image.filename == "test_image.png"
        assert stored_image.image_type == ImageType.PICTURE
        assert stored_image.image_index == 1
        assert stored_image.file_size > 0
        assert stored_image.width == 100
        assert stored_image.height == 100
        assert stored_image.format == "PNG"

    @pytest.mark.asyncio
    async def test_store_images_disabled(self, test_settings, sample_image):
        """Test image storage when disabled."""
        test_settings.images_enabled = False
        storage_manager = ImageStorageManager(test_settings)
        
        doc_id = uuid.uuid4()
        image_paths = [sample_image]
        
        stored_images = await storage_manager.store_images(doc_id, image_paths)
        
        assert len(stored_images) == 0

    @pytest.mark.asyncio
    async def test_store_images_empty_list(self, storage_manager):
        """Test image storage with empty image list."""
        doc_id = uuid.uuid4()
        image_paths = []
        
        stored_images = await storage_manager.store_images(doc_id, image_paths)
        
        assert len(stored_images) == 0

    @pytest.mark.asyncio
    async def test_get_image_path(self, storage_manager):
        """Test getting full image path from relative path."""
        doc_id = uuid.uuid4()
        relative_path = "2025/01/19/test_image.png"
        
        full_path = await storage_manager.get_image_path(doc_id, relative_path)
        
        expected_path = storage_manager.base_path / relative_path
        assert full_path == expected_path

    @pytest.mark.asyncio
    async def test_cleanup_document_images(self, storage_manager, sample_image):
        """Test cleanup of document images."""
        doc_id = uuid.uuid4()
        
        # First store some images
        await storage_manager.store_images(doc_id, [sample_image])
        
        # Verify storage path exists and has files
        storage_path = storage_manager._get_storage_path(doc_id)
        assert storage_path.exists()
        assert len(list(storage_path.iterdir())) > 0
        
        # Cleanup images
        deleted_count = await storage_manager.cleanup_document_images(doc_id)
        
        assert deleted_count == 1
        # Directory should be removed if empty
        assert not storage_path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_document(self, storage_manager):
        """Test cleanup of non-existent document images."""
        doc_id = uuid.uuid4()
        
        deleted_count = await storage_manager.cleanup_document_images(doc_id)
        
        assert deleted_count == 0

    def test_get_storage_stats(self, storage_manager):
        """Test storage statistics."""
        stats = storage_manager.get_storage_stats()
        
        assert 'base_path' in stats
        assert 'total_files' in stats
        assert 'total_size_bytes' in stats
        assert 'total_size_mb' in stats
        
        assert stats['base_path'] == str(storage_manager.base_path)
        assert isinstance(stats['total_files'], int)
        assert isinstance(stats['total_size_bytes'], int)
        assert isinstance(stats['total_size_mb'], float)


class TestStoredImage:
    """Test cases for StoredImage class."""

    def test_stored_image_creation(self):
        """Test StoredImage creation."""
        path = Path("test/path.png")
        stored_image = StoredImage(
            path=path,
            filename="test.png",
            image_type=ImageType.TABLE,
            image_index=1,
            file_size=1024,
            width=100,
            height=200,
            format="PNG",
            metadata={"test": "value"}
        )
        
        assert stored_image.path == path
        assert stored_image.filename == "test.png"
        assert stored_image.image_type == ImageType.TABLE
        assert stored_image.image_index == 1
        assert stored_image.file_size == 1024
        assert stored_image.width == 100
        assert stored_image.height == 200
        assert stored_image.format == "PNG"
        assert stored_image.metadata == {"test": "value"}

    def test_stored_image_repr(self):
        """Test StoredImage string representation."""
        path = Path("test/path.png")
        stored_image = StoredImage(
            path=path,
            filename="test.png",
            image_type=ImageType.PICTURE,
            image_index=1,
            file_size=1024
        )
        
        repr_str = repr(stored_image)
        assert "StoredImage" in repr_str
        assert "test/path.png" in repr_str
        assert "PICTURE" in repr_str
        assert "1024" in repr_str
