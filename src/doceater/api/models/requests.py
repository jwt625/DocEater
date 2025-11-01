"""API request models."""

from typing import Any

from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    """Request model for document upload metadata."""

    description: str | None = Field(None, description="Optional document description")
    tags: list[str] | None = Field(default_factory=list, description="Document tags")
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="Additional metadata"
    )


class SearchRequest(BaseModel):
    """Request model for multimodal search."""

    query: str = Field(
        ..., description="Search query text", min_length=1, max_length=1000
    )
    top_k: int = Field(
        default=10, description="Number of results to return", ge=1, le=100
    )
    include_images: bool = Field(default=True, description="Include image results")
    include_text: bool = Field(default=True, description="Include text results")
    document_ids: list[str] | None = Field(
        None, description="Limit search to specific documents"
    )
    similarity_threshold: float = Field(
        default=0.0, description="Minimum similarity score", ge=0.0, le=1.0
    )


class SimilarSearchRequest(BaseModel):
    """Request model for finding similar documents."""

    document_id: str = Field(..., description="Reference document ID")
    top_k: int = Field(
        default=5, description="Number of similar documents to return", ge=1, le=50
    )
    similarity_threshold: float = Field(
        default=0.1, description="Minimum similarity score", ge=0.0, le=1.0
    )


class ReprocessRequest(BaseModel):
    """Request model for reprocessing document embeddings."""

    force: bool = Field(
        default=False, description="Force reprocessing even if embeddings exist"
    )
    include_images: bool = Field(default=True, description="Reprocess image embeddings")
    include_text: bool = Field(default=True, description="Reprocess text embeddings")
