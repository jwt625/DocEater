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
from typing import TYPE_CHECKING, Any

from sentence_transformers import SentenceTransformer
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Global lock to prevent concurrent model loading across all instances
_global_model_lock = asyncio.Lock()


class EmbeddingService:
    """Jina CLIP v2 embedding service for DocEater API."""

    def __init__(self) -> None:
        """Initialize the embedding service."""
        self._model: SentenceTransformer | None = None
        self._model_lock = asyncio.Lock()

    async def _get_model(self) -> SentenceTransformer:
        """Get or load the Jina CLIP v2 model (thread-safe)."""
        if self._model is None:
            # Use global lock to prevent racing conditions across all instances
            async with _global_model_lock:
                if self._model is None:  # Double-check pattern
                    logger.info("Loading Jina CLIP v2 model...")
                    # Load in a thread to avoid blocking the event loop
                    loop = asyncio.get_event_loop()
                    self._model = await loop.run_in_executor(
                        None,
                        self._load_model_simple,
                    )
                    logger.info("✅ Jina CLIP v2 model loaded successfully")
        return self._model

    def _load_model_simple(self) -> SentenceTransformer:
        """Load the model with simple retry logic to handle racing conditions."""
        import torch

        # Use local cache if available, otherwise download
        model_name = "jinaai/jina-clip-v2"

        try:
            # Load model - let sentence-transformers handle caching
            model = SentenceTransformer(model_name, trust_remote_code=True)

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.to("cuda")

            logger.info("Model loaded successfully")
            return model

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    async def generate_text_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        embeddings = await self.generate_text_embeddings([text])
        return embeddings[0]

    async def generate_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple text strings with batch processing."""
        if not texts:
            return []

        model = await self._get_model()
        total_texts = len(texts)
        logger.debug(f"Generating embeddings for {total_texts} text chunks")

        # Batch processing to avoid GPU memory overflow
        # Adjust batch size based on available GPU memory and text length
        batch_size = self._calculate_optimal_batch_size(texts)
        logger.debug(f"Using batch size: {batch_size} for {total_texts} texts")

        all_embeddings = []

        # Process in batches
        for i in range(0, total_texts, batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_texts + batch_size - 1) // batch_size

            logger.debug(
                f"Processing batch {batch_num}/{total_batches} ({len(batch_texts)} texts)"
            )

            # Generate embeddings for this batch in a thread to avoid blocking
            loop = asyncio.get_event_loop()

            def encode_batch(batch: list[str]) -> Any:
                return model.encode(batch, normalize_embeddings=True)

            batch_embeddings = await loop.run_in_executor(
                None, encode_batch, batch_texts
            )

            # Convert numpy arrays to lists and add to results
            batch_result = [embedding.tolist() for embedding in batch_embeddings]
            all_embeddings.extend(batch_result)

            # Force garbage collection between batches to free GPU memory
            import gc

            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

        logger.debug(
            f"✅ Generated {len(all_embeddings)} text embeddings in {total_batches} batches"
        )
        return all_embeddings

    def _calculate_optimal_batch_size(self, texts: list[str]) -> int:
        """Calculate optimal batch size based on text characteristics and available GPU memory."""
        if not texts:
            return 4

        # Estimate average text length
        avg_length = sum(len(text) for text in texts) / len(texts)

        # Very conservative batch size calculation for Jina CLIP v2
        # This model has extremely high memory requirements
        if avg_length > 2000:  # Very long texts
            return 1  # Process one at a time
        elif avg_length > 1000:  # Long texts
            return 2
        elif avg_length > 500:  # Medium texts
            return 4
        else:  # Short texts
            return 8

        # Maximum safety limit: never exceed 8 texts per batch
        # Jina CLIP v2 requires significant GPU memory even for small batches

    async def generate_image_embedding(self, image: Any) -> list[float]:
        """Generate embedding for a single image."""
        embeddings = await self.generate_image_embeddings([image])
        return embeddings[0]

    async def generate_image_embeddings(self, images: list[Any]) -> list[list[float]]:
        """Generate embeddings for multiple images with batch processing."""
        if not images:
            return []

        model = await self._get_model()
        total_images = len(images)
        logger.debug(f"Generating embeddings for {total_images} images")

        # Batch processing for images (images are generally more memory-intensive)
        batch_size = min(16, total_images)  # Conservative batch size for images
        logger.debug(f"Using batch size: {batch_size} for {total_images} images")

        all_embeddings = []

        # Process in batches
        for i in range(0, total_images, batch_size):
            batch_images = images[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_images + batch_size - 1) // batch_size

            logger.debug(
                f"Processing image batch {batch_num}/{total_batches} ({len(batch_images)} images)"
            )

            # Generate embeddings for this batch in a thread to avoid blocking
            loop = asyncio.get_event_loop()

            def encode_image_batch(batch: list[Any]) -> Any:
                return model.encode(batch, normalize_embeddings=True)

            batch_embeddings = await loop.run_in_executor(
                None, encode_image_batch, batch_images
            )

            # Convert numpy arrays to lists and add to results
            batch_result = [embedding.tolist() for embedding in batch_embeddings]
            all_embeddings.extend(batch_result)

            # Force garbage collection between batches to free GPU memory
            import gc

            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()

        logger.debug(
            f"✅ Generated {len(all_embeddings)} image embeddings in {total_batches} batches"
        )
        return all_embeddings

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
            results["image_results"] = list(image_results)

        total_results = len(results["text_results"]) + len(results["image_results"])
        logger.info(f"Multimodal search returned {total_results} total results")
        return results
