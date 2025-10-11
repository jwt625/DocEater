"""Image serving endpoints."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from loguru import logger

from ...config import get_settings
from ...database import get_db_manager
from ...models import DocumentImage
from ..auth import get_current_user, TokenData

router = APIRouter()


@router.get("/images/{image_id}")
async def get_image(
    image_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    settings = Depends(get_settings)
):
    """
    Serve an extracted image by ID.
    
    Returns the image file with appropriate headers for browser display.
    Supports PNG, JPEG, and WebP formats.
    """
    
    try:
        db_manager = get_db_manager()
        
        # Get image record from database
        async with db_manager.get_session() as session:
            from sqlalchemy import select
            
            query = select(DocumentImage).where(DocumentImage.id == image_id)
            result = await session.execute(query)
            image_record = result.scalar_one_or_none()
            
            if not image_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Image not found"
                )
            
            # Check if file exists
            image_path = Path(image_record.file_path)
            if not image_path.exists():
                logger.error(f"Image file not found: {image_path}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Image file not found on disk"
                )
            
            # Determine media type from file extension
            media_type_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.webp': 'image/webp',
            }
            
            media_type = media_type_map.get(
                image_path.suffix.lower(),
                'application/octet-stream'
            )
            
            # Return file response
            return FileResponse(
                path=image_path,
                media_type=media_type,
                filename=f"image_{image_id}{image_path.suffix}",
                headers={
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                    "X-Image-Type": image_record.image_type.value,
                    "X-Page-Number": str(image_record.page_number),
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve image {image_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve image: {str(e)}"
        )
