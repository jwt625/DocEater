"""Health check and system status endpoints."""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import text

from ...config import get_settings
from ...database import get_db_manager
from ..auth import TokenData, get_current_user, get_current_user_optional
from ..models.responses import HealthResponse, StatsResponse

router = APIRouter()

# Track startup time for uptime calculation
startup_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    current_user: TokenData | None = Depends(get_current_user_optional),
    settings=Depends(get_settings),
):
    """
    System health check endpoint.

    Returns the overall health status of the DocEater system including:
    - Database connectivity
    - Embedding model status
    - Disk space availability
    - System uptime and memory usage
    """

    # Check database connectivity
    db_status = "healthy"
    try:
        db_manager = get_db_manager()
        async with db_manager.get_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    # Check embedding model (placeholder - will implement with embedding service)
    model_status = "not_loaded"  # TODO: Check actual model status

    # Check disk space (simplified)
    disk_status = "healthy"  # TODO: Implement actual disk space check

    # Calculate uptime
    uptime_seconds = time.time() - startup_time

    # Get memory usage (simplified)
    memory_usage_mb = 0.0  # TODO: Implement actual memory usage check

    # Determine overall status
    overall_status = "healthy"
    if db_status != "healthy":
        overall_status = "unhealthy"
    elif model_status == "error":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(UTC),
        version="1.0.0",
        database=db_status,
        embedding_model=model_status,
        disk_space=disk_status,
        uptime_seconds=uptime_seconds,
        memory_usage_mb=memory_usage_mb,
    )


@router.get("/stats", response_model=StatsResponse)
async def system_stats(
    current_user: TokenData = Depends(get_current_user), settings=Depends(get_settings)
):
    """
    Get system statistics.

    Returns detailed statistics about:
    - Document counts and processing status
    - Embedding counts and storage usage
    - Performance metrics

    Requires authentication.
    """

    db_manager = get_db_manager()

    try:
        async with db_manager.get_session() as session:
            # Document statistics
            from ...models import DocumentStatus

            # Total documents
            result = await session.execute(text("SELECT COUNT(*) FROM documents"))
            total_documents = result.scalar() or 0

            # Processing documents
            result = await session.execute(
                text("SELECT COUNT(*) FROM documents WHERE status = :status"),
                {"status": DocumentStatus.PROCESSING},
            )
            processing_documents = result.scalar() or 0

            # Failed documents
            result = await session.execute(
                text("SELECT COUNT(*) FROM documents WHERE status = :status"),
                {"status": DocumentStatus.FAILED},
            )
            failed_documents = result.scalar() or 0

            # Embedding statistics
            result = await session.execute(text("SELECT COUNT(*) FROM text_embeddings"))
            total_text_embeddings = result.scalar() or 0

            result = await session.execute(
                text("SELECT COUNT(*) FROM image_embeddings")
            )
            total_image_embeddings = result.scalar() or 0

            result = await session.execute(text("SELECT COUNT(*) FROM document_images"))
            total_images = result.scalar() or 0

            # Storage statistics (simplified)
            total_storage_mb = 0.0  # TODO: Calculate actual storage usage
            database_size_mb = 0.0  # TODO: Get actual database size
            images_storage_mb = 0.0  # TODO: Calculate images storage

            # Performance statistics (placeholder)
            avg_processing_time_seconds = 0.0  # TODO: Calculate from processing logs
            avg_search_time_ms = 0.0  # TODO: Track search performance

            return StatsResponse(
                total_documents=total_documents,
                processing_documents=processing_documents,
                failed_documents=failed_documents,
                total_text_embeddings=total_text_embeddings,
                total_image_embeddings=total_image_embeddings,
                total_images=total_images,
                total_storage_mb=total_storage_mb,
                database_size_mb=database_size_mb,
                images_storage_mb=images_storage_mb,
                avg_processing_time_seconds=avg_processing_time_seconds,
                avg_search_time_ms=avg_search_time_ms,
            )

    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system statistics",
        )
