"""
Embedding service for DocEater using Jina CLIP v2 for multimodal embeddings.

This module provides the embedding service that integrates with the DocEater API
to generate embeddings for text and images, and perform similarity search using PGVector.
"""

from .service import EmbeddingService, get_embedding_service

__all__ = ["EmbeddingService", "get_embedding_service"]
