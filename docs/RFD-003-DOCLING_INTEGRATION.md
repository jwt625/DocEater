# Docling Integration

This document describes how DocEater integrates with the official Docling library for enhanced document processing.

## Overview

DocEater uses a local installation of Docling from the official repository at https://github.com/DS4SD/docling instead of the pip-installed version. This allows us to:

- Use the latest features and improvements
- Enable advanced options like `--enrich_formula`
- Have more control over the configuration
- Potentially contribute back to the project

## Setup

### Local Docling Installation

The Docling library is cloned and installed locally:

```bash
# Clone the official repository
git clone https://github.com/DS4SD/docling.git external/docling

# Install in development mode
uv pip install -e ./external/docling
```

### Integration Architecture

The integration consists of two main components:

1. **DoclingWrapper** (`src/doceater/docling_wrapper.py`): A wrapper class that configures Docling with enhanced options
2. **DocumentProcessor** (`src/doceater/processor.py`): Updated to use the wrapper instead of direct Docling calls

## Features

### Formula Enrichment

The integration enables Docling's formula enrichment feature (`--enrich_formula`) by default. This enhances the processing of mathematical formulas and equations in documents.

```python
# Enable formula enrichment (default)
processor = DocumentProcessor(enable_formula_enrichment=True)

# Disable if needed
processor = DocumentProcessor(enable_formula_enrichment=False)
```

### Supported Formats

The integration supports all Docling-compatible formats:

- PDF (`.pdf`)
- Microsoft Word (`.docx`)
- PowerPoint (`.pptx`)
- HTML (`.html`)
- Markdown (`.md`)
- Plain text (`.txt`)
- Excel (`.xlsx`)
- CSV (`.csv`)
- JSON (`.json`)
- XML (`.xml`)

### Enhanced Configuration

The DoclingWrapper provides enhanced configuration options:

```python
from src.doceater.docling_wrapper import DoclingWrapper

wrapper = DoclingWrapper(enable_formula_enrichment=True)

# Get supported formats
formats = wrapper.get_supported_formats()

# Convert document
result = wrapper.convert_document("path/to/document.pdf")

# Convert to markdown
markdown = wrapper.convert_to_markdown("path/to/document.pdf")
```

## Configuration Options

The wrapper configures Docling with the following options:

- **OCR**: Enabled for image-based content
- **Table Structure**: Enabled for table extraction
- **Formula Enrichment**: Configurable (enabled by default)
- **Code Enrichment**: Disabled (can be enabled if needed)
- **Picture Description**: Disabled (can be enabled if needed)
- **Picture Classification**: Disabled (can be enabled if needed)

## Usage in DocEater

The DocumentProcessor automatically uses the enhanced Docling configuration:

```python
from src.doceater.processor import DocumentProcessor

# Create processor with formula enrichment
processor = DocumentProcessor(enable_formula_enrichment=True)

# Process a file
success = await processor.process_file(Path("document.pdf"))
```

## Dependencies

The local Docling installation brings its own dependencies. The main DocEater `pyproject.toml` no longer includes `docling>=2.0.0` as a dependency since we use the local version.

## Maintenance

### Updating Docling

To update to the latest version of Docling:

```bash
cd external/docling
git pull origin main
uv pip install -e .
```

### Manual Model Download

For air-gapped environments or when automatic model download fails, models can be downloaded manually from HuggingFace:

#### Required Models

**Primary Source (Recommended):**
- **Consolidated Repository**: `https://huggingface.co/ds4sd/docling-models/tree/main/model_artifacts`
- **Contains**: All Docling models in one repository under `model_artifacts/` directory

**Individual Model Repositories (Alternative):**

1. **Layout Model** (Critical - required for PDF processing)
   - **HuggingFace URL**: `https://huggingface.co/ds4sd/docling-layout-old`
   - **Local Directory**: `~/.cache/docling/models/ds4sd--docling-layout-old/`
   - **Required Files**: `model.safetensors`, `config.json`, `preprocessor_config.json`

2. **TableFormer Model** (Important - for table structure)
   - **HuggingFace URL**: `https://huggingface.co/ds4sd/docling-tableformer`
   - **Local Directory**: `~/.cache/docling/models/ds4sd--docling-tableformer/`

3. **Code Formula Model** (Important - for formula enrichment)
   - **HuggingFace URL**: `https://huggingface.co/ds4sd/docling-code-formula`
   - **Local Directory**: `~/.cache/docling/models/ds4sd--docling-code-formula/`

4. **Picture Classifier Model** (Optional)
   - **HuggingFace URL**: `https://huggingface.co/ds4sd/docling-picture-classifier`
   - **Local Directory**: `~/.cache/docling/models/ds4sd--docling-picture-classifier/`

#### Download Methods

**Method 1: HuggingFace CLI (Recommended)**
```bash
# Install huggingface-hub if not already installed
pip install huggingface-hub

# Download each model
huggingface-cli download ds4sd/docling-layout-old --local-dir ~/.cache/docling/models/ds4sd--docling-layout-old
huggingface-cli download ds4sd/docling-tableformer --local-dir ~/.cache/docling/models/ds4sd--docling-tableformer
huggingface-cli download ds4sd/docling-code-formula --local-dir ~/.cache/docling/models/ds4sd--docling-code-formula
huggingface-cli download ds4sd/docling-picture-classifier --local-dir ~/.cache/docling/models/ds4sd--docling-picture-classifier
```

**Method 2: Git LFS**
```bash
# Create the cache directory
mkdir -p ~/.cache/docling/models

# Clone each repository
cd ~/.cache/docling/models
git clone https://huggingface.co/ds4sd/docling-layout-old ds4sd--docling-layout-old
git clone https://huggingface.co/ds4sd/docling-tableformer ds4sd--docling-tableformer
git clone https://huggingface.co/ds4sd/docling-code-formula ds4sd--docling-code-formula
git clone https://huggingface.co/ds4sd/docling-picture-classifier ds4sd--docling-picture-classifier
```

**Method 3: Manual Web Download**
1. Visit each HuggingFace URL in a web browser
2. Download all files from the repository
3. Place files in the corresponding local directory
4. Ensure the directory structure matches the expected format

#### Expected Directory Structure
```
~/.cache/docling/models/
├── ds4sd--docling-layout-old/
│   ├── model.safetensors
│   ├── config.json
│   ├── preprocessor_config.json
│   └── [other files]
├── ds4sd--docling-tableformer/
│   ├── [model files]
├── ds4sd--docling-code-formula/
│   ├── [model files]
└── ds4sd--docling-picture-classifier/
    ├── [model files]
```

#### Configuration with Local Models
```python
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

# Configure to use local models
pipeline_options = PdfPipelineOptions(
    do_ocr=False,
    do_table_structure=True,
    do_formula_enrichment=True,
    artifacts_path="~/.cache/docling/models"
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)
```

### Testing Integration

The integration can be tested by running document processing operations. The system will log when Docling is initialized with the enhanced configuration.

## Benefits

1. **Latest Features**: Access to the newest Docling capabilities
2. **Enhanced Processing**: Formula enrichment and other advanced features
3. **Better Control**: Fine-tuned configuration for DocEater's needs
4. **Flexibility**: Easy to modify and extend the integration
5. **Performance**: Optimized settings for document processing workflows

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the local Docling is properly installed with `uv pip install -e ./external/docling`
2. **Missing Dependencies**: The local Docling installation should handle all required dependencies
3. **Configuration Issues**: Check the DoclingWrapper initialization logs
4. **Model Download Failures**:
   - Error: `401 Client Error: Unauthorized for url: https://huggingface.co/api/models/ds4sd/docling-layout-old`
   - Solution: Download models manually using the instructions above
5. **Missing Model Files**:
   - Error: `Missing safe tensors file: ~/.cache/docling/models/model.safetensors`
   - Solution: Ensure all required model files are downloaded to the correct directories

### Logs

The integration provides detailed logging:

```
INFO | Initialized Docling converter with formula enrichment: True
INFO | Converting document with Docling: /path/to/document.pdf
INFO | Successfully converted document: /path/to/document.pdf
```

## Future Enhancements

Potential improvements to the integration:

1. **Additional Enrichment Options**: Enable code and picture processing
2. **Custom Models**: Integration with custom Docling models
3. **Batch Processing**: Optimized batch document processing
4. **Caching**: Cache converted documents for faster reprocessing
5. **Streaming**: Support for streaming large document processing
