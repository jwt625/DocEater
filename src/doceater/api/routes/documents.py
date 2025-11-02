"""Document management endpoints."""

from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from loguru import logger
from sqlalchemy.exc import IntegrityError

from ...config import get_settings
from ...database import get_db_manager
from ...models import Document, DocumentStatus
from ..auth import TokenData, get_current_user, require_write
from ..models.responses import (
    DocumentListResponse,
    DocumentResponse,
)
from ..services import DocumentProcessingService

router = APIRouter()


def validate_file_size(file: UploadFile, max_size_mb: int) -> None:
    """Validate uploaded file size."""
    if hasattr(file.file, "seek") and hasattr(file.file, "tell"):
        # Get file size
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        max_size_bytes = max_size_mb * 1024 * 1024
        if size > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File size ({size} bytes) exceeds maximum allowed size ({max_size_mb} MB)",
            )


async def save_upload_file(upload_file: UploadFile, temp_dir: Path) -> Path:
    """Save uploaded file to temporary location."""
    # Create temp directory if it doesn't exist
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Create temporary file with original filename
    temp_file = temp_dir / f"upload_{upload_file.filename}"

    try:
        # Stream file to disk to avoid loading into memory
        with open(temp_file, "wb") as f:
            while chunk := await upload_file.read(64 * 1024):  # 64KB chunks
                f.write(chunk)

        return temp_file
    except Exception as e:
        # Clean up on error
        if temp_file.exists():
            temp_file.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}",
        )


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    description: str | None = Form(None, description="Document description"),
    current_user: TokenData = Depends(require_write),
    settings=Depends(get_settings),
):
    """
    Upload and process a PDF document.

    Accepts a PDF file upload and starts processing it through the DocEater pipeline:
    1. Validates file size and type
    2. Saves file to temporary location
    3. Creates document record in database
    4. Starts background processing (Docling + embeddings)

    Returns the document record with processing status.
    """

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    # Validate file size
    validate_file_size(file, settings.upload_max_size_mb)

    # Save uploaded file
    temp_dir = Path(settings.temp_upload_dir)
    try:
        temp_file = await save_upload_file(file, temp_dir)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(e)}",
        )

    try:
        # Create document record
        db_manager = get_db_manager()

        # Calculate file hash and size
        import hashlib

        file_size = temp_file.stat().st_size

        with open(temp_file, "rb") as f:
            content_hash = hashlib.sha256(f.read()).hexdigest()

        # Create document in database
        document = await db_manager.create_document(
            file_path=str(temp_file),
            filename=file.filename,
            content_hash=content_hash,
            file_size=file_size,
            mime_type="application/pdf",
        )

        # Start background processing
        processing_service = DocumentProcessingService(settings)
        processing_service.start_background_processing(document.id, temp_file)
        logger.info(f"Started background processing for document {document.id}")

        # Return document response
        response = DocumentResponse(
            id=document.id,
            filename=document.filename,
            file_size=document.file_size,
            mime_type=document.mime_type,
            status=document.status,
            created_at=document.created_at,
            updated_at=document.updated_at,
            markdown_content=document.markdown_content,
            page_count=None,  # TODO: Extract from processing
            text_embedding_count=0,
            image_embedding_count=0,
            image_count=0,
            metadata={},
        )

        # Note: temp file cleanup is handled by the background processing service
        # after document processing is complete

        return response

    except IntegrityError as e:
        # Handle duplicate file constraint violations
        if temp_file.exists():
            try:
                temp_file.unlink()
                logger.debug(
                    f"Cleaned up temporary file after duplicate error: {temp_file}"
                )
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to clean up temporary file after duplicate error {temp_file}: {cleanup_error}"
                )

        # Check if it's a duplicate file path constraint
        if "ix_documents_file_path" in str(e) or "duplicate key value" in str(e):
            logger.warning(f"Duplicate file upload attempted: {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A document with the filename '{file.filename}' has already been uploaded. Please rename the file or check if it was already processed.",
            )
        else:
            # Other integrity errors
            logger.error(f"Database integrity error during document upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid document data. Please check your file and try again.",
            )

    except Exception as e:
        # Clean up temp file on error
        if temp_file.exists():
            try:
                temp_file.unlink()
                logger.debug(f"Cleaned up temporary file after error: {temp_file}")
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to clean up temporary file after error {temp_file}: {cleanup_error}"
                )
        logger.error(f"Failed to process uploaded document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: DocumentStatus | None = Query(None, description="Filter by status"),
    current_user: TokenData = Depends(get_current_user),
    settings=Depends(get_settings),
):
    """
    List documents with pagination and filtering.

    Returns a paginated list of documents with optional status filtering.
    """

    db_manager = get_db_manager()

    try:
        async with db_manager.get_session() as session:
            from sqlalchemy import func, select

            # Build query
            query = select(Document)
            count_query = select(func.count(Document.id))

            if status_filter:
                query = query.where(Document.status == status_filter)
                count_query = count_query.where(Document.status == status_filter)

            # Get total count
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            # Apply pagination
            offset = (page - 1) * page_size
            query = (
                query.offset(offset)
                .limit(page_size)
                .order_by(Document.created_at.desc())
            )

            # Execute query
            result = await session.execute(query)
            documents = result.scalars().all()

            # Convert to response models
            document_responses = []
            for doc in documents:
                # TODO: Get embedding and image counts
                document_responses.append(
                    DocumentResponse(
                        id=doc.id,
                        filename=doc.filename,
                        file_size=doc.file_size,
                        mime_type=doc.mime_type,
                        status=doc.status,
                        created_at=doc.created_at,
                        updated_at=doc.updated_at,
                        markdown_content=doc.markdown_content,
                        page_count=None,
                        text_embedding_count=0,
                        image_embedding_count=0,
                        image_count=0,
                        metadata={},
                    )
                )

            return DocumentListResponse(
                documents=document_responses,
                total=total,
                page=page,
                page_size=page_size,
                has_next=(offset + page_size) < total,
            )

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}",
        )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    settings=Depends(get_settings),
):
    """
    Get document details by ID.

    Returns detailed information about a specific document including
    processing status, content, and embedding statistics.
    """

    db_manager = get_db_manager()

    try:
        document = await db_manager.get_document_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )

        # TODO: Get embedding and image counts
        return DocumentResponse(
            id=document.id,
            filename=document.filename,
            file_size=document.file_size,
            mime_type=document.mime_type,
            status=document.status,
            created_at=document.created_at,
            updated_at=document.updated_at,
            markdown_content=document.markdown_content,
            page_count=None,
            text_embedding_count=0,
            image_embedding_count=0,
            image_count=0,
            metadata={},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}",
        )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    current_user: TokenData = Depends(require_write),
    settings=Depends(get_settings),
):
    """
    Delete a document and all associated data.

    Removes the document record, embeddings, images, and files.
    This operation cannot be undone.
    """

    db_manager = get_db_manager()

    try:
        # Check if document exists
        document = await db_manager.get_document_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )

        # TODO: Delete associated files and embeddings
        await db_manager.delete_document(document_id)

        return {"message": "Document deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        )
