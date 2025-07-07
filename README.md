# DocEater 🍽️

A background service that watches folders for new files, converts them to Markdown using Docling, and stores content with metadata in PostgreSQL for future semantic search capabilities.

## Features

- **Automatic File Monitoring**: Watches specified folders for new PDF files
- **Document Conversion**: Converts PDFs to Markdown using Docling with formula enrichment
- **Database Storage**: Stores documents and metadata in PostgreSQL
- **CLI Interface**: Easy-to-use command-line interface for manual operations
- **Error Handling**: Robust error handling with partial content recovery
- **Type Safety**: Fully typed Python codebase with strict mypy checking

## Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL with database created
- uv package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd DocEater
```

2. Install dependencies:
```bash
uv sync --dev
```

3. Set up configuration:
```bash
cp .env.example .env
# Edit .env with your database settings
```

4. Initialize the database:
```bash
uv run doceat init
```

### Usage

#### Watch a folder for new files:
```bash
uv run doceat watch ~/Downloads
```

#### Manually ingest a file:
```bash
uv run doceat ingest document.pdf
```

#### List processed documents:
```bash
uv run doceat list
```

#### Show document details:
```bash
uv run doceat show <document-id>
```

#### Check system status:
```bash
uv run doceat status
```

## Configuration

Configuration is managed through environment variables or a `.env` file:

- `DOCEATER_DATABASE_URL`: PostgreSQL connection URL
- `DOCEATER_WATCH_FOLDER`: Folder to monitor (default: ~/Downloads)
- `DOCEATER_MAX_FILE_SIZE_MB`: Maximum file size to process (default: 100MB)
- `DOCEATER_LOG_LEVEL`: Logging level (default: INFO)

See `.env.example` for all available options.

## Development

### Code Quality

The project uses modern Python tooling:

- **ruff**: Fast linting and formatting
- **mypy**: Static type checking
- **pre-commit**: Git hooks for code quality

Run quality checks:
```bash
uv run ruff check src/
uv run mypy src/
```

### Testing

```bash
uv run pytest
```

## Architecture

The MVP consists of:

- **File Watcher**: Monitors folders using watchdog
- **Document Processor**: Converts files using Docling
- **Database Layer**: PostgreSQL with async SQLAlchemy
- **CLI Interface**: Typer-based command interface

## Roadmap

- [ ] Semantic search with embeddings (Phase 2)
- [ ] Document linking and relationships
- [ ] Web UI for document browsing
- [ ] Support for additional file formats
- [ ] LLM integration for document analysis

## License

MIT License