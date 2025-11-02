"""
Embedding service for DocEater using Jina CLIP v2 for multimodal embeddings.

This service provides:
1. Text and image embedding generation using Jina CLIP v2
2. Vector similarity search using PGVector
3. Integration with DocEater's database models
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from PIL import Image
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Jina CLIP v2 embedding service for DocEater API."""

    def __init__(self):
        """Initialize the embedding service."""
        self._model: SentenceTransformer | None = None
        self._model_lock = asyncio.Lock()

    async def _get_model(self) -> SentenceTransformer:
        """Get or load the Jina CLIP v2 model (thread-safe)."""
        if self._model is None:
            async with self._model_lock:
                if self._model is None:  # Double-check pattern
                    logger.info("Loading Jina CLIP v2 model...")
                    # Load in a thread to avoid blocking the event loop
                    loop = asyncio.get_event_loop()
                    self._model = await loop.run_in_executor(
                        None,
                        lambda: SentenceTransformer(
                            "jinaai/jina-clip-v2", trust_remote_code=True
                        ),
                    )
                    logger.info("✅ Jina CLIP v2 model loaded successfully")
        return self._model

    async def generate_text_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        embeddings = await self.generate_text_embeddings([text])
        return embeddings[0]

    async def generate_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple text strings."""
        if not texts:
            return []

        model = await self._get_model()
        logger.debug(f"Generating embeddings for {len(texts)} text chunks")

        # Generate embeddings in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True),
        )

        # Convert numpy arrays to lists
        result = [embedding.tolist() for embedding in embeddings]
        logger.debug(f"✅ Generated {len(result)} text embeddings")
        return result

    async def generate_image_embedding(self, image: Image.Image) -> list[float]:
        """Generate embedding for a single image."""
        embeddings = await self.generate_image_embeddings([image])
        return embeddings[0]

    async def generate_image_embeddings(
        self, images: list[Image.Image]
    ) -> list[list[float]]:
        """Generate embeddings for multiple images."""
        if not images:
            return []

        model = await self._get_model()
        logger.debug(f"Generating embeddings for {len(images)} images")

        # Generate embeddings in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(images, normalize_embeddings=True),
        )

        # Convert numpy arrays to lists
        result = [embedding.tolist() for embedding in embeddings]
        logger.debug(f"✅ Generated {len(result)} image embeddings")
        return result

    async def search_similar_text(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        include_document_info: bool = True,
    ) -> list[dict[str, Any]]:
        """Search for similar text chunks using vector similarity."""
        # Generate query embedding
        query_embedding = await self.generate_text_embedding(query)

        # Build the SQL query
        if include_document_info:
            sql_query = text("""
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
                WHERE 1 - (te.embedding <=> :query_embedding) >= :similarity_threshold
                ORDER BY te.embedding <=> :query_embedding
                LIMIT :top_k
            """)
        else:
            sql_query = text("""
                SELECT
                    te.id,
                    te.chunk_text,
                    te.page_number,
                    te.bbox_coordinates,
                    te.chunk_index,
                    te.created_at,
                    te.document_id,
                    1 - (te.embedding <=> :query_embedding) as similarity_score
                FROM text_embeddings te
                WHERE 1 - (te.embedding <=> :query_embedding) >= :similarity_threshold
                ORDER BY te.embedding <=> :query_embedding
                LIMIT :top_k
            """)

        # Execute the query
        # Convert embedding list to string format for PostgreSQL vector type
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        result = await session.execute(
            sql_query,
            {
                "query_embedding": embedding_str,
                "similarity_threshold": similarity_threshold,
                "top_k": top_k,
            },
        )

        # Convert results to dictionaries
        rows = result.fetchall()
        results = []
        for row in rows:
            result_dict = dict(row._mapping)
            results.append(result_dict)

        logger.info(
            f"Found {len(results)} similar text chunks for query: '{query[:50]}...'"
        )
        return results

    async def search_similar_images(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        include_document_info: bool = True,
    ) -> list[dict[str, Any]]:
        """Search for similar images using text query and vector similarity."""
        # Generate query embedding
        query_embedding = await self.generate_text_embedding(query)

        # Build the SQL query
        if include_document_info:
            sql_query = text("""
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
                WHERE 1 - (ie.embedding <=> :query_embedding) >= :similarity_threshold
                ORDER BY ie.embedding <=> :query_embedding
                LIMIT :top_k
            """)
        else:
            sql_query = text("""
                SELECT
                    ie.id,
                    ie.description,
                    ie.ocr_text,
                    ie.created_at,
                    ie.document_image_id,
                    1 - (ie.embedding <=> :query_embedding) as similarity_score
                FROM image_embeddings ie
                WHERE 1 - (ie.embedding <=> :query_embedding) >= :similarity_threshold
                ORDER BY ie.embedding <=> :query_embedding
                LIMIT :top_k
            """)

        # Execute the query
        # Convert embedding list to string format for PostgreSQL vector type
        embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
        result = await session.execute(
            sql_query,
            {
                "query_embedding": embedding_str,
                "similarity_threshold": similarity_threshold,
                "top_k": top_k,
            },
        )

        # Convert results to dictionaries
        rows = result.fetchall()
        results = []
        for row in rows:
            result_dict = dict(row._mapping)
            results.append(result_dict)

        logger.info(f"Found {len(results)} similar images for query: '{query[:50]}...'")
        return results

    async def search_multimodal(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        include_text: bool = True,
        include_images: bool = True,
    ) -> dict[str, Any]:
        """Search both text and images, returning combined results."""
        results = {"text_results": [], "image_results": [], "query": query}

        # Search text if requested
        if include_text:
            text_results = await self.search_similar_text(
                session, query, top_k, similarity_threshold
            )
            results["text_results"] = text_results

        # Search images if requested
        if include_images:
            image_results = await self.search_similar_images(
                session, query, top_k, similarity_threshold
            )
            results["image_results"] = image_results

        total_results = len(results["text_results"]) + len(results["image_results"])
        logger.info(f"Multimodal search returned {total_results} total results")
        return results
