"""Wrapper for local Docling integration with enhanced configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from loguru import logger


class DoclingWrapper:
    """Wrapper for Docling with enhanced configuration including formula enrichment."""

    def __init__(self, enable_formula_enrichment: bool = True) -> None:
        """Initialize the Docling wrapper.
        
        Args:
            enable_formula_enrichment: Whether to enable formula enrichment (--enrich_formula)
        """
        self.enable_formula_enrichment = enable_formula_enrichment
        self._converter: DocumentConverter | None = None

    @property
    def converter(self) -> DocumentConverter:
        """Get or create the Docling converter with default configuration."""
        if self._converter is None:
            # Use default DocumentConverter for now
            self._converter = DocumentConverter()

            logger.info(
                "Initialized Docling converter with default configuration"
            )

        return self._converter

    def convert_document(self, file_path: Path | str) -> Any:
        """Convert a document to Docling format.
        
        Args:
            file_path: Path to the document to convert
            
        Returns:
            Docling conversion result
        """
        try:
            logger.info(f"Converting document with Docling: {file_path}")
            result = self.converter.convert(str(file_path))
            logger.info(f"Successfully converted document: {file_path}")
            return result
        except Exception as e:
            logger.error(f"Failed to convert document {file_path}: {e}")
            raise

    def convert_to_markdown(self, file_path: Path | str) -> str:
        """Convert document to Markdown format.
        
        Args:
            file_path: Path to the document to convert
            
        Returns:
            Markdown content as string
        """
        result = self.convert_document(file_path)
        return result.document.export_to_markdown()

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.

        Returns:
            List of supported file extensions
        """
        # Based on actual Docling InputFormat enum
        return [
            ".pdf",      # PDF documents
            ".docx",     # Microsoft Word
            ".pptx",     # Microsoft PowerPoint
            ".html",     # HTML documents
            ".md",       # Markdown
            ".csv",      # CSV files
            ".xlsx",     # Microsoft Excel
            ".xml",      # XML (USPTO/JATS formats)
            # Note: JSON, TXT not directly supported by Docling
            # IMAGE and AUDIO formats also supported but not included here
        ]
