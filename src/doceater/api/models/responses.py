"""API response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ...models import DocumentStatus, ImageType


class DocumentResponse(BaseModel):
    """Response model for document details."""
    
    id: UUID = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    status: DocumentStatus = Field(..., description="Processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # Content
    markdown_content: Optional[str] = Field(None, description="Extracted markdown content")
    page_count: Optional[int] = Field(None, description="Number of pages")
    
    # Statistics
    text_embedding_count: int = Field(default=0, description="Number of text embeddings")
    image_embedding_count: int = Field(default=0, description="Number of image embeddings")
    image_count: int = Field(default=0, description="Number of extracted images")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentListResponse(BaseModel):
    """Response model for document list."""
    
    documents: List[DocumentResponse] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")


class ProcessingStatusResponse(BaseModel):
    """Response model for document processing status."""
    
    document_id: UUID = Field(..., description="Document ID")
    status: DocumentStatus = Field(..., description="Current processing status")
    progress: float = Field(..., description="Processing progress (0.0-1.0)")
    stage: str = Field(..., description="Current processing stage")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")


class SearchResult(BaseModel):
    """Individual search result."""
    
    id: UUID = Field(..., description="Result ID")
    document_id: UUID = Field(..., description="Source document ID")
    document_filename: str = Field(..., description="Source document filename")
    content_type: str = Field(..., description="Result type: 'text' or 'image'")
    content: str = Field(..., description="Text content or image description")
    similarity_score: float = Field(..., description="Similarity score (0.0-1.0)")
    
    # Grounding information
    page_number: Optional[int] = Field(None, description="Page number")
    bbox_coordinates: Optional[Dict[str, float]] = Field(None, description="Bounding box coordinates")
    
    # For image results
    image_id: Optional[UUID] = Field(None, description="Image ID for image results")
    image_url: Optional[str] = Field(None, description="Image URL for image results")
    image_type: Optional[ImageType] = Field(None, description="Image type")


class SearchResponse(BaseModel):
    """Response model for search results."""
    
    query: str = Field(..., description="Original search query")
    results: List[SearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Total number of results found")
    search_time_ms: float = Field(..., description="Search execution time in milliseconds")
    
    # Result breakdown
    text_results: int = Field(..., description="Number of text results")
    image_results: int = Field(..., description="Number of image results")


class EmbeddingInfo(BaseModel):
    """Embedding information."""
    
    id: UUID = Field(..., description="Embedding ID")
    content_type: str = Field(..., description="Content type: 'text' or 'image'")
    content_preview: str = Field(..., description="Preview of content")
    embedding_dimension: int = Field(..., description="Embedding vector dimension")
    created_at: datetime = Field(..., description="Creation timestamp")


class EmbeddingResponse(BaseModel):
    """Response model for document embeddings."""
    
    document_id: UUID = Field(..., description="Document ID")
    text_embeddings: List[EmbeddingInfo] = Field(..., description="Text embeddings")
    image_embeddings: List[EmbeddingInfo] = Field(..., description="Image embeddings")
    total_embeddings: int = Field(..., description="Total number of embeddings")


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="API version")
    
    # Component health
    database: str = Field(..., description="Database connection status")
    embedding_model: str = Field(..., description="Embedding model status")
    disk_space: str = Field(..., description="Disk space status")
    
    # Performance metrics
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    memory_usage_mb: float = Field(..., description="Memory usage in MB")


class StatsResponse(BaseModel):
    """Response model for system statistics."""
    
    # Document statistics
    total_documents: int = Field(..., description="Total number of documents")
    processing_documents: int = Field(..., description="Documents currently processing")
    failed_documents: int = Field(..., description="Documents with processing errors")
    
    # Embedding statistics
    total_text_embeddings: int = Field(..., description="Total text embeddings")
    total_image_embeddings: int = Field(..., description="Total image embeddings")
    total_images: int = Field(..., description="Total extracted images")
    
    # Storage statistics
    total_storage_mb: float = Field(..., description="Total storage used in MB")
    database_size_mb: float = Field(..., description="Database size in MB")
    images_storage_mb: float = Field(..., description="Images storage in MB")
    
    # Performance statistics
    avg_processing_time_seconds: float = Field(..., description="Average document processing time")
    avg_search_time_ms: float = Field(..., description="Average search time in milliseconds")


class ErrorResponse(BaseModel):
    """Response model for API errors."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
