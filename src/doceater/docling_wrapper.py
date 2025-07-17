"""Wrapper for local Docling integration with enhanced configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from loguru import logger


class DoclingWrapper:
    """Wrapper for Docling with enhanced configuration including formula enrichment and image extraction."""

    def __init__(
        self,
        enable_formula_enrichment: bool = True,
        enable_image_extraction: bool = True,
        images_scale: float = 2.0,
    ) -> None:
        """Initialize the Docling wrapper.

        Args:
            enable_formula_enrichment: Whether to enable formula enrichment (--enrich_formula)
            enable_image_extraction: Whether to extract images from documents
            images_scale: Scale factor for extracted images (1.0 = 72 DPI, 2.0 = 144 DPI)
        """
        self.enable_formula_enrichment = enable_formula_enrichment
        self.enable_image_extraction = enable_image_extraction
        self.images_scale = images_scale
        self._converter: DocumentConverter | None = None

    @property
    def converter(self) -> DocumentConverter:
        """Get or create the Docling converter with enhanced local model configuration."""
        if self._converter is None:
            # Configure local models path
            artifacts_path = os.path.expanduser("~/.cache/docling/models")

            # Configure PDF pipeline options with local models
            pipeline_options = PdfPipelineOptions(
                do_ocr=False,  # Disable OCR for now (can be enabled if needed)
                do_table_structure=True,  # Enable table structure detection
                do_formula_enrichment=self.enable_formula_enrichment,  # Formula enrichment
                artifacts_path=artifacts_path,  # Use local models
                # Image extraction options
                images_scale=self.images_scale,  # Scale for extracted images
                generate_page_images=False,  # Don't extract full page images
                generate_picture_images=self.enable_image_extraction,  # Extract only figure images
            )

            # Create converter with enhanced configuration
            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

            logger.info(
                f"Initialized Docling converter with local models from {artifacts_path}, "
                f"formula enrichment: {self.enable_formula_enrichment}, "
                f"image extraction: {self.enable_image_extraction} (scale: {self.images_scale}x)"
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

    def convert_to_markdown_with_images(
        self,
        file_path: Path | str,
        output_dir: Path | str | None = None,
        image_mode: str = "referenced"
    ) -> tuple[str, list[Path]]:
        """Convert document to Markdown with image extraction.

        Args:
            file_path: Path to the document to convert
            output_dir: Directory to save extracted images (default: same as document)
            image_mode: "embedded" for base64 images, "referenced" for file references

        Returns:
            Tuple of (markdown_content, list_of_image_paths)
        """
        if not self.enable_image_extraction:
            logger.warning("Image extraction is disabled. Use enable_image_extraction=True")
            return self.convert_to_markdown(file_path), []

        result = self.convert_document(file_path)

        # Set up output directory for images
        if output_dir is None:
            output_dir = Path(file_path).parent
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Extract and save images
        extracted_images = self.extract_images(result, output_dir)

        # Convert to markdown with image references
        if image_mode == "embedded":
            markdown_content = result.document.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
        else:
            markdown_content = result.document.export_to_markdown(image_mode=ImageRefMode.REFERENCED)

        logger.info(f"Extracted {len(extracted_images)} images to {output_dir}")
        return markdown_content, extracted_images

    def extract_images(self, conversion_result: Any, output_dir: Path) -> list[Path]:
        """Extract images from conversion result and save to files.

        Args:
            conversion_result: Docling conversion result
            output_dir: Directory to save images

        Returns:
            List of paths to saved image files
        """
        extracted_images = []
        doc_filename = conversion_result.input.file.stem

        # Note: We don't extract page images anymore, only figures and tables

        # Save images of figures and tables
        table_counter = 0
        picture_counter = 0

        for element, _level in conversion_result.document.iterate_items():
            try:
                if isinstance(element, TableItem):
                    table_counter += 1
                    element_image_filename = output_dir / f"{doc_filename}-table-{table_counter}.png"
                    with element_image_filename.open("wb") as fp:
                        element.get_image(conversion_result.document).save(fp, "PNG")
                    extracted_images.append(element_image_filename)
                    logger.debug(f"Saved table image: {element_image_filename}")

                elif isinstance(element, PictureItem):
                    picture_counter += 1
                    element_image_filename = output_dir / f"{doc_filename}-picture-{picture_counter}.png"
                    with element_image_filename.open("wb") as fp:
                        element.get_image(conversion_result.document).save(fp, "PNG")
                    extracted_images.append(element_image_filename)
                    logger.debug(f"Saved picture image: {element_image_filename}")

            except Exception as e:
                logger.warning(f"Failed to extract image from element: {e}")
                continue

        return extracted_images

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
