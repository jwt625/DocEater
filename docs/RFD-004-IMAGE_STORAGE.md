# RFD-004: Image Storage and Database Integration

**Status:** Proposal  
**Author:** DocEater Team  
**Created:** 2025-01-17  
**Updated:** 2025-01-17

## Summary

This RFD proposes implementing proper storage and database integration for images extracted from documents during Docling processing. Currently, DocEater can extract images from documents but does not store them persistently or track them in the database.

## Problem Statement

### Current State

✅ **Working**: Docling integration extracts images successfully
- 90 figures extracted from 115-page test document
- High-quality images (2x resolution, 144 DPI)
- Smart filtering (figures only, no page images)

❌ **Missing**: Image storage and database integration
- Images extracted to temporary directories
- No persistent storage strategy
- No database tracking of extracted images
- No image metadata storage
- No cleanup or organization

### Impact

Without proper image storage:
1. **Data Loss**: Extracted images are lost after processing
2. **Incomplete Search**: Text search without visual context
3. **Poor User Experience**: Cannot view document images
4. **Wasted Processing**: Re-extraction needed for image access
5. **Storage Chaos**: No organized image file management

## Proposed Solution

### Architecture Overview

```
Document Processing Flow:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PDF/DOCX      │───▶│  Docling Extract │───▶│  Text + Images  │
│   Document      │    │  Text & Images   │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Database      │◀───│  Store Metadata  │◀───│  Organize &     │
│   - documents   │    │  & References    │    │  Store Images   │
│   - images      │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### 1. Database Schema Extension

#### New Table: `document_images`

```sql
CREATE TABLE document_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- File information
    image_path TEXT NOT NULL,           -- Relative path from images root
    filename TEXT NOT NULL,             -- Original extracted filename
    image_type TEXT NOT NULL,           -- 'picture', 'table', 'page'
    image_index INTEGER NOT NULL,       -- Order within document
    
    -- Image properties
    file_size BIGINT NOT NULL,
    width INTEGER,                      -- Image width in pixels
    height INTEGER,                     -- Image height in pixels
    format TEXT,                        -- 'PNG', 'JPEG', etc.
    
    -- Processing metadata
    extraction_method TEXT,             -- 'docling', 'manual', etc.
    quality_score FLOAT,               -- Optional quality assessment
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_document_images_document_id (document_id),
    INDEX idx_document_images_type (image_type),
    INDEX idx_document_images_created (created_at)
);
```

#### Enhanced Metadata Storage

```sql
-- Add image-related metadata to existing document_metadata table
-- Examples:
-- key='image_count', value='90'
-- key='image_extraction_enabled', value='true'
-- key='image_total_size', value='15728640'  -- bytes
```

### 2. File Storage Strategy

#### Directory Structure

```
{DOCEATER_DATA_DIR}/
├── documents/                    # Original documents
│   ├── 2025/01/17/
│   │   ├── document1.pdf
│   │   └── document2.docx
├── images/                       # Extracted images
│   ├── 2025/01/17/
│   │   ├── {document_id}/
│   │   │   ├── picture-1.png
│   │   │   ├── picture-2.png
│   │   │   ├── table-1.png
│   │   │   └── metadata.json     # Image extraction metadata
│   │   └── {document_id_2}/
├── cache/                        # Temporary processing
└── config/                       # Configuration files
```

#### Storage Configuration

```python
# Configuration options
class ImageStorageConfig:
    enabled: bool = True
    base_path: Path = Path("~/doceater_data/images")
    max_image_size: int = 50 * 1024 * 1024  # 50MB per image
    allowed_formats: list[str] = ["PNG", "JPEG", "WEBP"]
    compression_quality: int = 85  # For JPEG compression
    organize_by_date: bool = True
    cleanup_failed_extractions: bool = True
```

### 3. Implementation Plan

#### Phase 1: Database Schema (Week 1)

1. **Create Migration**
   - Add `document_images` table
   - Add indexes for performance
   - Update database manager with image operations

2. **Database Manager Updates**
   ```python
   class DatabaseManager:
       async def create_document_image(
           self, document_id: UUID, image_path: str, 
           filename: str, image_type: str, **kwargs
       ) -> DocumentImage
       
       async def get_document_images(
           self, document_id: UUID
       ) -> list[DocumentImage]
       
       async def delete_document_images(
           self, document_id: UUID
       ) -> None
   ```

#### Phase 2: Storage Implementation (Week 2)

1. **Image Storage Manager**
   ```python
   class ImageStorageManager:
       def __init__(self, config: ImageStorageConfig)
       
       async def store_images(
           self, document_id: UUID, images: list[Path]
       ) -> list[StoredImage]
       
       async def get_image_path(
           self, document_id: UUID, image_id: UUID
       ) -> Path
       
       async def cleanup_document_images(
           self, document_id: UUID
       ) -> None
   ```

2. **File Organization**
   - Date-based directory structure
   - Document ID subdirectories
   - Atomic file operations
   - Cleanup on processing failure

#### Phase 3: DocumentProcessor Integration (Week 3)

1. **Enhanced Processing**
   ```python
   async def process_file(self, file_path: Path) -> bool:
       # ... existing code ...
       
       # Convert with image extraction
       if self.enable_image_extraction:
           markdown_content, extracted_images = await self.convert_with_images(file_path)
           
           # Store images persistently
           stored_images = await self.image_storage.store_images(
               document.id, extracted_images
           )
           
           # Save image metadata to database
           for stored_image in stored_images:
               await self.db_manager.create_document_image(
                   document.id, stored_image.path, stored_image.filename,
                   stored_image.type, **stored_image.metadata
               )
       else:
           markdown_content = await self.convert_to_markdown(file_path)
   ```

#### Phase 4: API and CLI Integration (Week 4)

1. **CLI Commands**
   ```bash
   # List document images
   doceater images list <document_id>
   
   # Export images
   doceater images export <document_id> --output-dir ./exported_images/
   
   # Cleanup orphaned images
   doceater images cleanup
   
   # Re-extract images for existing document
   doceater images re-extract <document_id>
   ```

2. **API Endpoints** (Future)
   ```
   GET /api/documents/{id}/images
   GET /api/images/{image_id}
   DELETE /api/documents/{id}/images
   ```

### 4. Configuration Options

#### Environment Variables

```bash
# Image storage configuration
DOCEATER_IMAGES_ENABLED=true
DOCEATER_IMAGES_BASE_PATH=~/doceater_data/images
DOCEATER_IMAGES_MAX_SIZE=52428800  # 50MB
DOCEATER_IMAGES_QUALITY=85
DOCEATER_IMAGES_ORGANIZE_BY_DATE=true
```

#### Config File

```yaml
# doceater.yaml
images:
  enabled: true
  storage:
    base_path: "~/doceater_data/images"
    max_image_size: 52428800  # 50MB
    organize_by_date: true
  processing:
    compression_quality: 85
    allowed_formats: ["PNG", "JPEG", "WEBP"]
  cleanup:
    cleanup_failed_extractions: true
    retention_days: 365  # Keep images for 1 year
```

### 5. Error Handling and Edge Cases

#### Storage Failures
- Graceful degradation when storage fails
- Continue text processing even if image storage fails
- Retry mechanisms for temporary failures
- Cleanup partial extractions

#### Disk Space Management
- Monitor available disk space
- Configurable size limits per document
- Automatic cleanup of old images
- Compression options for large images

#### Concurrent Processing
- Atomic file operations
- Lock-free image storage
- Unique filename generation
- Race condition prevention

### 6. Testing Strategy

#### Unit Tests
- Database operations for images
- File storage and retrieval
- Error handling scenarios
- Configuration validation

#### Integration Tests
- End-to-end document processing with images
- Database consistency checks
- File system cleanup verification
- Performance with large documents

#### Performance Tests
- Processing time with/without image extraction
- Storage space efficiency
- Concurrent document processing
- Large document handling (1000+ images)

### 7. Migration Strategy

#### Existing Documents
```python
# Migration script for existing documents
async def migrate_existing_documents():
    """Re-process existing documents to extract images."""
    documents = await db.get_documents_without_images()
    
    for document in documents:
        if document.status == DocumentStatus.COMPLETED:
            # Re-extract images from existing documents
            await reprocess_document_images(document)
```

#### Backward Compatibility
- Image extraction is optional (configurable)
- Existing text-only processing continues to work
- Gradual rollout with feature flags

### 8. Monitoring and Observability

#### Metrics
- Images extracted per document
- Storage space usage
- Processing time impact
- Error rates for image extraction

#### Logging
```python
logger.info(f"Extracted {len(images)} images for document {doc_id}")
logger.info(f"Stored images: {total_size_mb:.1f}MB in {storage_path}")
logger.warning(f"Image extraction failed for {doc_id}: {error}")
```

## Benefits

1. **Complete Document Capture**: Store both text and visual content
2. **Enhanced Search**: Future image-based search capabilities
3. **Better User Experience**: View document images alongside text
4. **Data Integrity**: Persistent storage prevents data loss
5. **Scalability**: Organized storage for thousands of documents
6. **Flexibility**: Configurable storage options and formats

## Risks and Mitigation

### Storage Space Growth
- **Risk**: Large storage requirements for image-heavy documents
- **Mitigation**: Compression, size limits, cleanup policies

### Processing Performance
- **Risk**: Slower processing with image extraction
- **Mitigation**: Configurable feature, async processing, optimization

### File System Complexity
- **Risk**: Complex file organization and cleanup
- **Mitigation**: Atomic operations, comprehensive testing, monitoring

## Future Enhancements

1. **Image Search**: OCR on extracted images for searchable text
2. **Image Analysis**: AI-powered image classification and tagging
3. **Thumbnail Generation**: Create thumbnails for quick preview
4. **Image Deduplication**: Detect and handle duplicate images
5. **Cloud Storage**: Support for S3, GCS, Azure Blob storage
6. **Image Compression**: Advanced compression algorithms
7. **Image Formats**: Support for additional formats (SVG, TIFF)

## Conclusion

Implementing proper image storage and database integration will complete the DocEater document processing pipeline, providing users with comprehensive document capture including both textual and visual content. The proposed solution is scalable, configurable, and maintains backward compatibility while adding significant value to the document processing workflow.
