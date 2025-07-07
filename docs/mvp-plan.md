# DocEater MVP Implementation Plan

## MVP Goals
Create a minimal but functional version with core document processing capabilities:
- Watch a single folder for PDF files
- Convert PDFs to Markdown using Docling with formula enrichment
- Store documents and metadata in PostgreSQL
- Provide basic CLI for manual operations
- Modular, type-safe, maintainable codebase

## Environment Setup

### Prerequisites Check ✅
- Python 3.13 available at `/opt/homebrew/bin/python3.13`
- uv package manager installed (v0.7.16)

### Setup Steps
1. Create virtual environment with Python 3.13
2. Initialize uv project
3. Set up development tools (ruff, mypy, pre-commit)

## MVP Architecture

```
src/doceater/
├── __init__.py              # Package initialization
├── config.py                # Configuration with Pydantic
├── models.py                # Database models (SQLAlchemy)
├── database.py              # Database connection and operations
├── processor.py             # Document processing with Docling
├── watcher.py               # File system monitoring
├── cli.py                   # CLI interface with Typer
└── main.py                  # Application entry point
```

## MVP Database Schema (Simplified)

```sql
-- Core documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type TEXT,
    markdown_content TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    status TEXT DEFAULT 'pending' -- 'pending', 'processing', 'completed', 'failed'
);

-- Simple metadata storage
CREATE TABLE document_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Processing logs
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    level TEXT NOT NULL, -- 'info', 'warning', 'error'
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at);
CREATE INDEX idx_document_metadata_key ON document_metadata(key);
CREATE INDEX idx_processing_logs_level ON processing_logs(level);
```

## MVP Implementation Steps

### Step 1: Project Foundation
```bash
# Create virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Initialize uv project
uv init --python 3.13
uv add typer rich pydantic pydantic-settings
uv add sqlalchemy[asyncio] asyncpg alembic
uv add docling watchdog aiofiles loguru
uv add --dev pytest pytest-asyncio ruff mypy pre-commit
```

### Step 2: Core Configuration (config.py)
- Pydantic settings with .env support
- Database connection settings
- Watch folder configuration (default: ~/Downloads)
- File processing settings
- Logging configuration

### Step 3: Database Layer (models.py, database.py)
- SQLAlchemy async models
- Database connection management
- Alembic migrations
- Basic CRUD operations

### Step 4: Document Processor (processor.py)
- Docling integration with --enrich-formula
- File metadata extraction
- Content hash calculation
- Error handling with partial content recovery
- Async processing

### Step 5: File Watcher (watcher.py)
- Watchdog integration for single folder
- PDF file filtering
- Event debouncing
- Queue management for processing

### Step 6: CLI Interface (cli.py)
- Typer-based commands
- Rich output formatting
- Basic commands:
  - `doceat init` - Initialize database
  - `doceat watch [folder]` - Start watching folder
  - `doceat ingest <file>` - Manual file ingestion
  - `doceat list` - List processed documents
  - `doceat show <doc_id>` - Show document content
  - `doceat status` - Show processing status

### Step 7: Application Entry Point (main.py)
- Async application setup
- Signal handling
- Graceful shutdown
- Error handling and logging

## MVP CLI Commands

```bash
# Initialize database and configuration
doceat init

# Start watching Downloads folder
doceat watch

# Watch specific folder
doceat watch /path/to/folder

# Manually ingest a file
doceat ingest document.pdf

# List all documents
doceat list

# Show document details
doceat show <document-id>

# Show processing status
doceat status

# Show configuration
doceat config show

# Set configuration
doceat config set watch_folder=/path/to/folder
```

## Development Workflow

### Code Quality Setup
```toml
# pyproject.toml
[tool.ruff]
target-version = "py313"
line-length = 88
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM", "TCH"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### Pre-commit Configuration
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## MVP Success Criteria

1. **Functional**: Can watch folder and process PDF files automatically
2. **Reliable**: Handles errors gracefully and logs issues
3. **Usable**: CLI provides clear feedback and useful commands
4. **Maintainable**: Clean, typed, modular code structure
5. **Extensible**: Easy to add embeddings and search in Phase 2

## Phase 2 Extensions (Post-MVP)

After MVP is working:
1. Add embedding generation (sentence-transformers)
2. Add pgvector for semantic search
3. Implement chunking strategies
4. Add search CLI commands
5. Add document linking capabilities

## Next Steps

1. Confirm MVP scope and approach
2. Set up development environment
3. Create project structure
4. Implement Step 1 (Project Foundation)
5. Build incrementally with testing at each step

Ready to start implementation?
