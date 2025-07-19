"""
DocEater - Background service for automatic document ingestion and semantic search.

A tool that watches folders for new files, converts them to Markdown using Docling,
and stores content with metadata in PostgreSQL for future semantic search capabilities.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "DocEater Team"
__email__ = "team@doceater.dev"

# Core exports for the MVP
from .config import Settings, get_settings
from .models import Document, DocumentImage, DocumentMetadata, ImageType, ProcessingLog

__all__ = [
    "Settings",
    "get_settings",
    "Document",
    "DocumentImage",
    "DocumentMetadata",
    "ImageType",
    "ProcessingLog",
]
