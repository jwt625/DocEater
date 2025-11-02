"""Search and retrieval endpoints."""

import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from ...config import get_settings
from ...database import get_db_manager
from ...embeddings.service import EmbeddingService
from ..auth import TokenData, get_current_user
from ..models.requests import SearchRequest, SimilarSearchRequest
from ..models.responses import SearchResponse, SearchResult

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    current_user: TokenData = Depends(get_current_user),
    settings=Depends(get_settings),
):
    """
    Perform multimodal search across documents.

    Searches both text and image embeddings using the provided query.
    Returns ranked results with grounding information (page numbers, bounding boxes).

    The search uses Jina CLIP v2 embeddings and PGVector cosine similarity.
    """
    start_time = time.time()

    logger.info(f"Search request received for query: '{request.query}'")

    try:
        # Initialize embedding service
        embedding_service = EmbeddingService()
        db_manager = get_db_manager()

        all_results = []
        text_count = 0
        image_count = 0

        async with db_manager.get_session() as session:
            # Search text embeddings if requested
            if request.include_text:
                text_results = await embedding_service.search_similar_text(
                    session=session,
                    query=request.query,
                    top_k=request.top_k,
                    similarity_threshold=request.similarity_threshold,
                    include_document_info=True,
                )
                logger.info(f"Text search returned {len(text_results)} results")
                if text_results:
                    logger.info(f"First result type: {type(text_results[0])}")
                    logger.info(
                        f"First result keys: {list(text_results[0].keys()) if isinstance(text_results[0], dict) else 'Not a dict'}"
                    )

                # Convert text results to SearchResult format
                for result in text_results:
                    # Results are dictionaries from embedding service
                    search_result = SearchResult(
                        id=result["id"],
                        document_id=result["document_id"],
                        document_filename=result["filename"],
                        content_type="text",
                        content=result["chunk_text"],
                        similarity_score=result["similarity_score"],
                        page_number=result.get("page_number"),
                        bbox_coordinates=result.get("bbox_coordinates"),
                        image_id=None,
                        image_url=None,
                        image_type=None,
                    )
                    all_results.append(search_result)
                    text_count += 1

            # Search image embeddings if requested
            if request.include_images:
                image_results = await embedding_service.search_similar_images(
                    session=session,
                    query=request.query,
                    top_k=request.top_k,
                    similarity_threshold=request.similarity_threshold,
                    include_document_info=True,
                )

                # Convert image results to SearchResult format
                for result in image_results:
                    # Results are dictionaries from embedding service
                    search_result = SearchResult(
                        id=result["id"],
                        document_id=result["document_id"],
                        document_filename=result["document_filename"],
                        content_type="image",
                        content=result.get("description", "Image content"),
                        similarity_score=result["similarity_score"],
                        page_number=None,  # Images don't have page numbers in current schema
                        bbox_coordinates=None,  # Images don't have bbox in current schema
                        image_id=result.get("document_image_id"),
                        image_url=f"/api/v1/images/{result.get('document_image_id')}",
                        image_type=None,  # TODO: Get from document_images table
                    )
                    all_results.append(search_result)
                    image_count += 1

        # Sort all results by similarity score (descending)
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)

        # Apply top_k limit across all results
        all_results = all_results[: request.top_k]

        search_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Search completed in {search_time_ms:.2f}ms: "
            f"{len(all_results)} results ({text_count} text, {image_count} images)"
        )

        return SearchResponse(
            query=request.query,
            results=all_results,
            total_results=len(all_results),
            search_time_ms=search_time_ms,
            text_results=text_count,
            image_results=image_count,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post("/search/similar", response_model=SearchResponse)
async def find_similar_documents(
    request: SimilarSearchRequest,
    current_user: TokenData = Depends(get_current_user),
    settings=Depends(get_settings),
):
    """
    Find documents similar to a given document.

    Uses the document's embeddings to find other documents with similar content.
    Useful for discovering related documents or duplicate detection.
    """
    start_time = time.time()

    logger.info(f"Similar search request received for document: {request.document_id}")

    try:
        db_manager = get_db_manager()
        document_uuid = UUID(request.document_id)

        all_results = []
        text_count = 0
        image_count = 0

        async with db_manager.get_session() as session:
            from sqlalchemy import text

            # Get reference embeddings from the specified document using raw SQL to handle vector type properly
            text_embeddings_query = text("""
                SELECT id, embedding::text as embedding_str
                FROM text_embeddings
                WHERE document_id = :document_id
            """)
            text_embeddings_result = await session.execute(
                text_embeddings_query, {"document_id": document_uuid}
            )
            ref_text_embeddings = text_embeddings_result.fetchall()

            image_embeddings_query = text("""
                SELECT ie.id, ie.embedding::text as embedding_str
                FROM image_embeddings ie
                JOIN document_images di ON ie.document_image_id = di.id
                WHERE di.document_id = :document_id
            """)
            image_embeddings_result = await session.execute(
                image_embeddings_query, {"document_id": document_uuid}
            )
            ref_image_embeddings = image_embeddings_result.fetchall()

            if not ref_text_embeddings and not ref_image_embeddings:
                logger.warning(
                    f"No embeddings found for document {request.document_id}"
                )
                return SearchResponse(
                    query=f"Similar to document {request.document_id}",
                    results=[],
                    total_results=0,
                    search_time_ms=(time.time() - start_time) * 1000,
                    text_results=0,
                    image_results=0,
                )

            # For each reference embedding, find similar embeddings from other documents
            seen_documents = set()

            # Search using text embeddings
            for ref_embedding in ref_text_embeddings:
                # The embedding is now a proper vector string from raw SQL
                embedding_value = ref_embedding.embedding_str

                similar_query = text("""
                    SELECT
                        te.id,
                        te.chunk_text,
                        te.page_number,
                        te.bbox_coordinates,
                        te.chunk_index,
                        te.created_at,
                        d.id as document_id,
                        d.filename,
                        1 - (te.embedding <=> :query_embedding) as similarity_score
                    FROM text_embeddings te
                    JOIN documents d ON te.document_id = d.id
                    WHERE d.id != :exclude_document_id
                    AND 1 - (te.embedding <=> :query_embedding) >= :similarity_threshold
                    ORDER BY te.embedding <=> :query_embedding
                    LIMIT :top_k
                """)

                result = await session.execute(
                    similar_query,
                    {
                        "query_embedding": embedding_value,
                        "exclude_document_id": document_uuid,
                        "similarity_threshold": request.similarity_threshold,
                        "top_k": request.top_k,
                    },
                )

                for row in result:
                    doc_id = row.document_id
                    if doc_id not in seen_documents:
                        search_result = SearchResult(
                            id=row.id,
                            document_id=doc_id,
                            document_filename=row.filename,
                            content_type="text",
                            content=row.chunk_text,
                            similarity_score=row.similarity_score,
                            page_number=row.page_number,
                            bbox_coordinates=row.bbox_coordinates,
                            image_id=None,
                            image_url=None,
                            image_type=None,
                        )
                        all_results.append(search_result)
                        seen_documents.add(doc_id)
                        text_count += 1

            # Search using image embeddings
            for ref_embedding in ref_image_embeddings:
                # The embedding is now a proper vector string from raw SQL
                embedding_value = ref_embedding.embedding_str

                similar_query = text("""
                    SELECT
                        ie.id,
                        ie.description,
                        ie.ocr_text,
                        ie.created_at,
                        di.id as document_image_id,
                        di.filename as image_filename,
                        di.image_path,
                        di.image_index,
                        di.width,
                        di.height,
                        d.id as document_id,
                        d.filename as document_filename,
                        1 - (ie.embedding <=> :query_embedding) as similarity_score
                    FROM image_embeddings ie
                    JOIN document_images di ON ie.document_image_id = di.id
                    JOIN documents d ON di.document_id = d.id
                    WHERE d.id != :exclude_document_id
                    AND 1 - (ie.embedding <=> :query_embedding) >= :similarity_threshold
                    ORDER BY ie.embedding <=> :query_embedding
                    LIMIT :top_k
                """)

                result = await session.execute(
                    similar_query,
                    {
                        "query_embedding": embedding_value,
                        "exclude_document_id": document_uuid,
                        "similarity_threshold": request.similarity_threshold,
                        "top_k": request.top_k,
                    },
                )

                for row in result:
                    doc_id = row.document_id
                    if doc_id not in seen_documents:
                        search_result = SearchResult(
                            id=row.id,
                            document_id=doc_id,
                            document_filename=row.document_filename,
                            content_type="image",
                            content=row.description or "Image content",
                            similarity_score=row.similarity_score,
                            page_number=None,
                            bbox_coordinates=None,
                            image_id=row.document_image_id,
                            image_url=f"/api/v1/images/{row.document_image_id}",
                            image_type=None,
                        )
                        all_results.append(search_result)
                        seen_documents.add(doc_id)
                        image_count += 1

        # Sort all results by similarity score (descending)
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)

        # Apply top_k limit across all results
        all_results = all_results[: request.top_k]

        search_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Similar search completed in {search_time_ms:.2f}ms: "
            f"{len(all_results)} results ({text_count} text, {image_count} images)"
        )

        return SearchResponse(
            query=f"Similar to document {request.document_id}",
            results=all_results,
            total_results=len(all_results),
            search_time_ms=search_time_ms,
            text_results=text_count,
            image_results=image_count,
        )

    except ValueError as e:
        logger.error(f"Invalid document ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document ID: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Similar search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Similar search failed: {str(e)}",
        )
