# DocEater

Production-ready document processing system with REST API and background file monitoring. Converts documents to Markdown using Docling, extracts images, and stores content in PostgreSQL for semantic search.

## Features

- **REST API** - FastAPI server for document management
- **Authentication** - JWT and API key support
- **File Monitoring** - Automatic folder watching for new documents
- **Document Processing** - Markdown conversion with formula enrichment
- **Image Extraction** - Automatic extraction and storage
- **Database** - PostgreSQL with pgvector for semantic search
- **CLI** - Complete command-line interface

## Quick Start

### Prerequisites
- Python 3.13+
- PostgreSQL with pgvector extension
- uv package manager

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/doceater.git
cd DocEater

# Install dependencies
uv sync --dev

# Download models (first time only)
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('jinaai/jina-clip-v2', trust_remote_code=True)"

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
uv run doceat init

# Start server
uv run doceat serve
```

API documentation: http://localhost:8000/docs

## Usage

### API Server
```bash
# Development
uv run doceat serve --reload

# Production
uv run doceat serve --workers 4
```

### File Processing
```bash
# Watch folder
uv run doceat watch ~/Downloads

# Process single file
uv run doceat ingest document.pdf
```

### Management
```bash
# List documents
uv run doceat list

# Show document
uv run doceat show <document-id>

# System status
uv run doceat status

# Image operations
uv run doceat images list
uv run doceat images export --document-id <id> --output ./images
```

## API Endpoints

### Documents
- `POST /api/v1/documents/upload` - Upload (max 100MB)
- `GET /api/v1/documents` - List with pagination
- `GET /api/v1/documents/{id}` - Get details
- `DELETE /api/v1/documents/{id}` - Delete

### System
- `GET /api/v1/health` - Health check
- `GET /api/v1/stats` - Statistics (authenticated)
- `GET /api/v1/images/{id}` - Serve images

### Search (Planned)
- `POST /api/v1/search` - Semantic search

## Configuration

Key environment variables:

- `DOCEATER_DATABASE_URL` - PostgreSQL connection
- `DOCEATER_JWT_SECRET_KEY` - JWT secret
- `DOCEATER_API_KEYS` - Service API keys
- `DOCEATER_IMAGES_BASE_PATH` - Image storage path
- `DOCEATER_WATCH_FOLDER` - Monitored folder

See `.env.example` for all options.

## Development

```bash
# Linting
uv run ruff check src/

# Type checking
uv run mypy src/

# Run tests
uv run pytest

# With coverage
uv run pytest --cov=src/doceater
```

## Architecture

- **FastAPI** - Async web framework
- **SQLAlchemy** - Database ORM with async support
- **Docling** - Document processing engine
- **PostgreSQL** - Database with pgvector extension
- **Pydantic** - Data validation
- **Typer** - CLI framework

## Status

**Production Ready:**
- REST API with authentication
- Document upload and processing
- Image extraction
- 83% test coverage (162 tests)

**In Development:**
- Semantic search with Jina CLIP embeddings
- Background processing pipeline
- Web UI

## License

MIT
