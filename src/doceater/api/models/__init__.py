"""API request and response models."""

# Request models
from .requests import (
    DocumentUploadRequest,
    ReprocessRequest,
    SearchRequest,
    SimilarSearchRequest,
)

# Response models
from .responses import (
    DocumentListResponse,
    DocumentResponse,
    EmbeddingInfo,
    EmbeddingResponse,
    ErrorResponse,
    HealthResponse,
    ProcessingStatusResponse,
    SearchResponse,
    SearchResult,
    StatsResponse,
)

__all__ = [
    # Request models
    "DocumentUploadRequest",
    "ReprocessRequest",
    "SearchRequest",
    "SimilarSearchRequest",
    # Response models
    "DocumentResponse",
    "DocumentListResponse",
    "EmbeddingInfo",
    "EmbeddingResponse",
    "ErrorResponse",
    "HealthResponse",
    "ProcessingStatusResponse",
    "SearchResponse",
    "SearchResult",
    "StatsResponse",
]
