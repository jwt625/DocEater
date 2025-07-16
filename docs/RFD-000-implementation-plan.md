# DocEater Implementation Plan

## Project Overview
DocEater is a background service that watches folders for new files, converts them to Markdown using Docling, and stores content with metadata in PostgreSQL with pgvector for semantic search.

## Technology Stack & Package Choices

### Core Language & Framework
- **Python 3.12+** - Latest Python with improved performance and type hints
- **asyncio** - For concurrent file processing and database operations
- **uv** - Fast Python package manager for dependency management

### Key Dependencies

#### CLI & Configuration
- **typer** - Modern CLI framework with excellent type hints and auto-completion
- **pydantic + pydantic-settings** - Type-safe configuration management with .env support
- **rich** - Beautiful terminal output and progress bars

#### File Watching & Processing
- **watchdog** - Cross-platform file system event monitoring
- **docling** - Document conversion with `--enrich-formula` support
- **aiofiles** - Async file operations

#### Database & Vector Storage
- **asyncpg** - High-performance async PostgreSQL driver
- **sqlalchemy[asyncio]** - ORM with async support
- **alembic** - Database migrations
- **pgvector** - PostgreSQL vector extension Python bindings

#### Embedding & ML
- **sentence-transformers** - Local embedding models (all-mpnet-base-v2 baseline, with option for bge-base-en or instructor-base)
- **torch** - PyTorch backend for transformers
- **numpy** - Numerical operations

#### Utilities
- **loguru** - Advanced logging with structured output
- **httpx** - HTTP client for future LLM endpoint integration

### Development Tools
- **pytest + pytest-asyncio** - Testing framework
- **ruff** - Fast Python linter and formatter (replaces black, isort, flake8)
- **mypy** - Strict type checking
- **pre-commit** - Git hooks for code quality and type checking

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   File Watcher  │───▶│ Processing Queue │───▶│  Document       │
│   (watchdog)    │    │  (asyncio.Queue) │    │  Processor      │
└─────────────────┘    └──────────────────┘    │  (docling)      │
                                               └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Interface │    │   Configuration  │    │   Embedding     │
│   (typer)       │    │   (pydantic)     │    │   Engine        │
└─────────────────┘    └──────────────────┘    │ (transformers)  │
                                               └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │   PostgreSQL    │
                                               │   + pgvector    │
                                               └─────────────────┘
```

## MVP (Minimal Viable Product) - Core Functionality First

### MVP Scope
A simplified version focusing on essential functionality:
1. **Basic file watching** - Monitor single folder for PDF files
2. **Document conversion** - Convert PDF to Markdown using Docling
3. **Simple storage** - Store in PostgreSQL without embeddings initially
4. **Basic CLI** - Manual ingestion and simple queries
5. **Modular architecture** - Easy to extend with embeddings and advanced features

### MVP Implementation Order
1. Project setup with Python 3.12 + uv + strict typing
2. Basic database schema (documents table only)
3. Docling integration for PDF conversion
4. Simple file watcher for one folder
5. Basic CLI commands (ingest, list, show)
6. Add embeddings and search as Phase 2

### Service Architecture Decision
- **User service by default** - Easier development and deployment
- **Configurable service type** - Add `--system-service` flag for system-wide installation
- **Easy migration path** - Service type can be changed via configuration

---

## Phase 1: Foundation & Core Infrastructure

### 1.1 Project Setup
**TODO:**
- [ ] Check Python 3.12+ installation via Homebrew
- [ ] Create virtual environment using Python 3.12
- [ ] Set up `uv` for fast package management
- [ ] Create modular package structure with `src/doceater/` layout
- [ ] Set up `pyproject.toml` with strict typing and development tools
- [ ] Configure pre-commit hooks with ruff and mypy
- [ ] Initialize git repository with comprehensive `.gitignore`
- [ ] Create basic `README.md` and `CONTRIBUTING.md`

**Modular Architecture:**
```
src/doceater/
├── __init__.py
├── config/          # Configuration management
├── database/        # Database models and operations
├── processing/      # Document processing pipeline
├── watching/        # File system monitoring
├── embedding/       # Embedding generation (Phase 2)
├── search/          # Search functionality (Phase 2)
├── cli/             # CLI commands and interface
├── service/         # Daemon/service functionality
└── utils/           # Shared utilities and types
```

**Strict Typing Setup:**
- Enable `strict = true` in mypy configuration
- Use `from __future__ import annotations` for forward references
- Comprehensive type hints for all functions and classes
- Pydantic models for data validation and serialization
- Generic types for reusable components

### 1.2 Configuration System
**TODO:**
- [ ] Design configuration schema with Pydantic models
- [ ] Implement `.env` file support with sensible defaults
- [ ] Add configuration validation and error handling
- [ ] Create configuration file templates
- [ ] Implement configuration reload functionality
- [ ] Add CLI command for configuration management

**Key Configuration Areas:**
- Database connection settings
- Watch folder paths (default: `~/Downloads`)
- File processing limits and filters
- Embedding model selection
- Logging configuration
- Service/daemon settings

### 1.3 Database Schema Design
**TODO:**
- [ ] Design PostgreSQL schema with proper indexing
- [ ] Create Alembic migration scripts
- [ ] Implement database connection management
- [ ] Add connection pooling and retry logic
- [ ] Create database initialization scripts
- [ ] Add schema validation and health checks

**Core Tables:**
```sql
-- Documents table
documents (
    id UUID PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    file_size BIGINT,
    mime_type TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    processed_at TIMESTAMP,
    status TEXT -- 'pending', 'processing', 'completed', 'failed'
)

-- Document content and embeddings
document_chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding vector(768), -- Adjust dimension based on model
    token_count INTEGER,
    created_at TIMESTAMP
)

-- Flexible metadata storage
document_metadata (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    key TEXT NOT NULL,
    value JSONB,
    created_at TIMESTAMP
)

-- Processing logs and errors
processing_logs (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    level TEXT, -- 'info', 'warning', 'error'
    message TEXT,
    details JSONB,
    created_at TIMESTAMP
)
```

### 1.4 Basic CLI Framework
**TODO:**
- [ ] Set up Typer-based CLI with subcommands
- [ ] Implement basic commands: `config`, `status`, `version`
- [ ] Add rich output formatting and progress bars
- [ ] Create help system and command documentation
- [ ] Add shell completion support
- [ ] Implement verbose/quiet modes

**Initial CLI Commands:**
```bash
doceat config show                    # Show current configuration
doceat config set key=value          # Set configuration values
doceat status                         # Show service status
doceat version                        # Show version info
```

## Phase 2: File Watching & Processing Pipeline

### 2.1 File Watcher Implementation
**TODO:**
- [ ] Implement watchdog-based folder monitoring
- [ ] Add file filtering by extension and patterns
- [ ] Handle file system events (created, modified, moved)
- [ ] Implement debouncing for rapid file changes
- [ ] Add recursive directory watching
- [ ] Create file event queue management

**Key Features:**
- Monitor multiple folders simultaneously
- Filter files by extension and exclude patterns
- Handle temporary files and incomplete downloads
- Debounce rapid file system events
- Queue files for processing

### 2.2 Document Processing Pipeline
**TODO:**
- [ ] Integrate Docling with `--enrich-formula` support
- [ ] Implement metadata extraction (file stats, MIME type)
- [ ] Add content hash calculation for deduplication
- [ ] Create error handling and partial content extraction
- [ ] Implement processing queue with concurrency limits
- [ ] Add progress tracking and status updates

**Processing Steps:**
1. File validation (size, type, accessibility)
2. Metadata extraction
3. Content hash calculation
4. Docling conversion to Markdown
5. Error logging with partial content recovery
6. Database storage

### 2.3 Error Handling & Resilience
**TODO:**
- [ ] Implement comprehensive error categorization
- [ ] Add retry logic with exponential backoff
- [ ] Create partial content extraction for corrupted files
- [ ] Log all errors with context in database
- [ ] Add file quarantine for problematic documents
- [ ] Implement processing status tracking

## Phase 3: Embedding & Vector Storage

### 3.1 Embedding Engine
**TODO:**
- [ ] Implement sentence-transformers integration
- [ ] Add model loading and caching
- [ ] Create text chunking with overlap strategy
- [ ] Implement batch embedding generation
- [ ] Add device selection (CPU/GPU/MPS)
- [ ] Create embedding dimension validation

**Chunking Strategy:**
- Default: 512 tokens with 50 token overlap
- Respect document structure (paragraphs, sections)
- Handle code blocks and formulas specially
- Maintain chunk metadata (position, type)

### 3.2 Vector Storage & Search
**TODO:**
- [ ] Implement pgvector integration
- [ ] Create vector indexing strategies
- [ ] Add similarity search functionality
- [ ] Implement search result ranking
- [ ] Add search filters (date, type, metadata)
- [ ] Create search performance optimization

### 3.3 CLI Search Commands
**TODO:**
- [ ] Implement semantic search command
- [ ] Add search result formatting
- [ ] Create search history and saved queries
- [ ] Add search filters and sorting options
- [ ] Implement search result export

**Search Commands:**
```bash
doceat search "query text"           # Semantic search
doceat search --similar-to doc_id    # Find similar documents
doceat search --filter type=pdf      # Filtered search
doceat search --export results.json  # Export results
```

## Phase 4: Service & Daemon Mode

### 4.1 Background Service
**TODO:**
- [ ] Implement daemon mode with proper signal handling
- [ ] Add service start/stop/restart commands
- [ ] Create PID file management
- [ ] Implement graceful shutdown
- [ ] Add service health monitoring
- [ ] Create service status reporting

### 4.2 System Integration
**TODO:**
- [ ] Create systemd service files (Linux)
- [ ] Create launchd plist files (macOS)
- [ ] Add installation/uninstallation scripts
- [ ] Implement log rotation
- [ ] Add service monitoring and alerting
- [ ] Create service configuration management

**Service Commands:**
```bash
doceat service start                 # Start background service
doceat service stop                  # Stop background service
doceat service status                # Show service status
doceat service install               # Install as system service
doceat service logs                  # Show service logs
```

## Phase 5: Advanced Features & CLI Enhancement

### 5.1 Document Management
**TODO:**
- [ ] Implement document versioning (git-like)
- [ ] Add document linking and relationships
- [ ] Create document export functionality
- [ ] Add document deletion and cleanup
- [ ] Implement document statistics and analytics

### 5.2 Enhanced CLI Operations
**TODO:**
- [ ] Add manual document ingestion
- [ ] Implement batch operations
- [ ] Create document linking commands
- [ ] Add configuration management UI
- [ ] Implement data export/import

**Advanced Commands:**
```bash
doceat ingest file.pdf               # Manual ingestion
doceat link doc1 doc2 --type related # Link documents
doceat export --format json         # Export data
doceat stats                         # Show statistics
doceat cleanup --older-than 30d     # Cleanup old documents
```

### 5.3 LLM Integration Preparation
**TODO:**
- [ ] Design LLM endpoint integration architecture
- [ ] Add HTTP client for LLM services
- [ ] Create prompt templates and management
- [ ] Implement LLM-assisted document analysis
- [ ] Add LLM response caching

## Phase 6: Testing & Documentation

### 6.1 Comprehensive Testing
**TODO:**
- [ ] Unit tests for all core components
- [ ] Integration tests for database operations
- [ ] End-to-end tests for file processing pipeline
- [ ] Performance tests for large document sets
- [ ] CLI command testing
- [ ] Service/daemon mode testing

### 6.2 Documentation & Deployment
**TODO:**
- [ ] Complete API documentation
- [ ] User guide and tutorials
- [ ] Installation and setup guides
- [ ] Configuration reference
- [ ] Troubleshooting guide
- [ ] Performance tuning guide

## Questions for Confirmation

1. **Package Choices**: Do you approve of the technology stack above?
2. **Database Schema**: Any modifications needed to the proposed schema?
3. **CLI Design**: Are the proposed commands and structure appropriate?
4. **Embedding Model**: Confirm `all-mpnet-base-v2` as default, or prefer different model?
5. **Service Type**: Confirm user service approach vs system service?
6. **Phase Priority**: Any phases you'd like to prioritize or modify?

## Next Steps

Once you confirm the plan, I'll:
1. Start with Phase 1.1 (Project Setup)
2. Create the basic project structure
3. Set up the development environment
4. Begin implementing the configuration system

Would you like me to proceed with this plan or make any modifications?
