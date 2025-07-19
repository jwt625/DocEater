"""Command-line interface for DocEater."""

from __future__ import annotations

import asyncio
import shutil
import sys
import uuid
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__
from .config import get_settings
from .database import get_db_manager
from .image_storage import ImageStorageManager
from .models import DocumentStatus, ImageType
from .watcher import FileWatcher

# Create CLI app
app = typer.Typer(
    name="doceat",
    help="DocEater - Background service for automatic document ingestion",
    add_completion=False,
)

# Rich console for output
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    settings = get_settings()

    # Remove default logger
    logger.remove()

    # Set log level
    log_level = "DEBUG" if verbose else settings.log_level

    # Add console logger
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Add file logger if configured
    if settings.log_file:
        logger.add(
            settings.log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="1 week",
        )


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"DocEater version {__version__}")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Force recreate database tables"),
) -> None:
    """Initialize database and configuration."""

    async def _init() -> None:
        settings = get_settings()
        db_manager = get_db_manager()

        console.print("🔧 Initializing DocEater...")

        try:
            if force:
                console.print("⚠️  Dropping existing tables...")
                await db_manager.drop_tables()

            console.print("📊 Creating database tables...")
            await db_manager.create_tables()

            console.print("✅ Database initialized successfully!")
            console.print(f"📁 Watch folder: {settings.watch_folder}")
            console.print(f"🔗 Database: {settings.database_url}")

        except Exception as e:
            console.print(f"❌ Failed to initialize database: {e}")
            raise typer.Exit(1)
        finally:
            await db_manager.close()

    asyncio.run(_init())


@app.command()
def watch(
    folder: str = typer.Argument(None, help="Folder to watch (default from config)"),
    process_existing: bool = typer.Option(
        False, "--process-existing", help="Process existing files before watching"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Start watching a folder for new files."""
    setup_logging(verbose)

    async def _watch() -> None:
        settings = get_settings()

        # Override watch folder if provided
        if folder:
            settings.watch_folder = str(Path(folder).expanduser().resolve())

        console.print(f"👀 Starting file watcher for: {settings.watch_folder}")

        watcher = FileWatcher(settings)

        try:
            # Process existing files if requested
            if process_existing:
                console.print("📂 Processing existing files...")
                await watcher.process_existing_files()

            # Start watching
            await watcher.start_watching()

            console.print("✅ File watcher started. Press Ctrl+C to stop.")

            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            console.print("\n🛑 Stopping file watcher...")
        except Exception as e:
            console.print(f"❌ Error: {e}")
            raise typer.Exit(1)
        finally:
            await watcher.stop_watching()
            await get_db_manager().close()

    asyncio.run(_watch())


@app.command()
def ingest(
    file_path: str = typer.Argument(..., help="Path to file to ingest"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Manually ingest a specific file."""
    setup_logging(verbose)

    async def _ingest() -> None:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            console.print(f"❌ File not found: {path}")
            raise typer.Exit(1)

        console.print(f"📄 Ingesting file: {path}")

        watcher = FileWatcher()

        try:
            success = await watcher.manual_process_file(path)

            if success:
                console.print("✅ File ingested successfully!")
            else:
                console.print("❌ Failed to ingest file")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"❌ Error: {e}")
            raise typer.Exit(1)
        finally:
            await get_db_manager().close()

    asyncio.run(_ingest())


@app.command()
def list(
    status: str = typer.Option(None, help="Filter by status (pending, processing, completed, failed)"),
    limit: int = typer.Option(20, help="Maximum number of documents to show"),
) -> None:
    """List processed documents."""

    async def _list() -> None:
        db_manager = get_db_manager()

        try:
            # Parse status filter
            status_filter = None
            if status:
                try:
                    status_filter = DocumentStatus(status.lower())
                except ValueError:
                    console.print(f"❌ Invalid status: {status}")
                    console.print("Valid statuses: pending, processing, completed, failed")
                    raise typer.Exit(1)

            # Get documents
            documents = await db_manager.list_documents(
                status=status_filter,
                limit=limit,
            )

            if not documents:
                console.print("📭 No documents found")
                return

            # Create table
            table = Table(title=f"Documents ({len(documents)} found)")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Filename", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Size", style="blue", justify="right")
            table.add_column("Created", style="magenta")

            for doc in documents:
                # Format file size
                size_mb = doc.file_size / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB"

                # Format status with color
                status_text = Text(doc.status.value)
                if doc.status == DocumentStatus.COMPLETED:
                    status_text.style = "green"
                elif doc.status == DocumentStatus.FAILED:
                    status_text.style = "red"
                elif doc.status == DocumentStatus.PROCESSING:
                    status_text.style = "yellow"
                else:
                    status_text.style = "blue"

                table.add_row(
                    str(doc.id)[:8] + "...",
                    doc.filename,
                    status_text,
                    size_str,
                    doc.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)

        except Exception as e:
            console.print(f"❌ Error: {e}")
            raise typer.Exit(1)
        finally:
            await db_manager.close()

    asyncio.run(_list())


@app.command()
def show(
    document_id: str = typer.Argument(..., help="Document ID to show"),
) -> None:
    """Show details of a specific document."""

    async def _show() -> None:
        db_manager = get_db_manager()

        try:
            # Parse document ID
            try:
                doc_uuid = uuid.UUID(document_id)
            except ValueError:
                console.print(f"❌ Invalid document ID: {document_id}")
                raise typer.Exit(1)

            # Get document
            document = await db_manager.get_document_by_id(doc_uuid)

            if not document:
                console.print(f"❌ Document not found: {document_id}")
                raise typer.Exit(1)

            # Display document details
            console.print(f"📄 Document: {document.filename}")
            console.print(f"🆔 ID: {document.id}")
            console.print(f"📁 Path: {document.file_path}")
            console.print(f"📊 Status: {document.status.value}")
            console.print(f"📏 Size: {document.file_size / (1024 * 1024):.1f} MB")
            console.print(f"🕒 Created: {document.created_at}")

            if document.processed_at:
                console.print(f"✅ Processed: {document.processed_at}")

            if document.mime_type:
                console.print(f"📋 MIME Type: {document.mime_type}")

            # Show content preview if available
            if document.markdown_content:
                console.print("\n📝 Content Preview:")
                preview = document.markdown_content[:500]
                if len(document.markdown_content) > 500:
                    preview += "..."
                console.print(preview)

        except Exception as e:
            console.print(f"❌ Error: {e}")
            raise typer.Exit(1)
        finally:
            await db_manager.close()

    asyncio.run(_show())


@app.command()
def status() -> None:
    """Show system status and statistics."""

    async def _status() -> None:
        settings = get_settings()
        db_manager = get_db_manager()

        try:
            console.print("📊 DocEater Status")
            console.print(f"📁 Watch folder: {settings.watch_folder}")
            console.print(f"🔗 Database: {settings.database_url}")

            # Get document counts by status
            for status in DocumentStatus:
                docs = await db_manager.list_documents(status=status, limit=1000)
                console.print(f"📄 {status.value.title()}: {len(docs)} documents")

        except Exception as e:
            console.print(f"❌ Error: {e}")
            raise typer.Exit(1)
        finally:
            await db_manager.close()

    asyncio.run(_status())


@app.command()
def images(
    action: str = typer.Argument(..., help="Action: list, export, cleanup, stats"),
    document_id: str = typer.Option(None, "--document-id", "-d", help="Document ID for list/export actions"),
    output_dir: str = typer.Option("./exported_images", "--output", "-o", help="Output directory for export"),
    image_type: str = typer.Option(None, "--type", "-t", help="Filter by image type (picture, table, etc.)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Manage document images."""
    setup_logging(verbose)

    async def _images() -> None:
        db_manager = get_db_manager()
        settings = get_settings()
        image_storage = ImageStorageManager(settings)

        try:
            if action == "list":
                if document_id:
                    # List images for specific document
                    try:
                        doc_uuid = uuid.UUID(document_id)
                    except ValueError:
                        console.print(f"❌ Invalid document ID: {document_id}")
                        raise typer.Exit(1) from None

                    # Get document info
                    document = await db_manager.get_document_by_id(doc_uuid)
                    if not document:
                        console.print(f"❌ Document not found: {document_id}")
                        raise typer.Exit(1) from None

                    # Get images
                    images = await db_manager.get_document_images(doc_uuid)

                    console.print(f"\n📄 Document: {document.filename}")
                    console.print(f"📁 Images: {len(images)}")

                    if images:
                        table = Table(title="Document Images")
                        table.add_column("Index", style="cyan")
                        table.add_column("Type", style="green")
                        table.add_column("Filename", style="blue")
                        table.add_column("Size", style="yellow")
                        table.add_column("Dimensions", style="magenta")

                        for image in images:
                            size_mb = image.file_size / (1024 * 1024)
                            dimensions = f"{image.width}x{image.height}" if image.width and image.height else "Unknown"
                            table.add_row(
                                str(image.image_index),
                                image.image_type.value,
                                image.filename,
                                f"{size_mb:.2f} MB",
                                dimensions
                            )

                        console.print(table)
                    else:
                        console.print("No images found for this document.")

                else:
                    # List all images with optional type filter
                    if image_type:
                        try:
                            img_type = ImageType(image_type.lower())
                            images = await db_manager.get_images_by_type(img_type, limit=50)
                            console.print(f"\n📷 Images of type '{image_type}': {len(images)}")
                        except ValueError:
                            console.print(f"❌ Invalid image type: {image_type}")
                            console.print("Valid types: picture, table, formula, chart, diagram, page")
                            raise typer.Exit(1) from None
                    else:
                        # Get recent images across all documents
                        images = await db_manager.get_images_by_type(ImageType.PICTURE, limit=25)
                        table_images = await db_manager.get_images_by_type(ImageType.TABLE, limit=25)
                        images.extend(table_images)
                        console.print(f"\n📷 Recent images: {len(images)}")

                    if images:
                        table = Table(title="All Images")
                        table.add_column("Document ID", style="cyan")
                        table.add_column("Type", style="green")
                        table.add_column("Filename", style="blue")
                        table.add_column("Created", style="yellow")

                        for image in images[:20]:  # Limit display
                            table.add_row(
                                str(image.document_id)[:8] + "...",
                                image.image_type.value,
                                image.filename,
                                image.created_at.strftime("%Y-%m-%d %H:%M")
                            )

                        console.print(table)
                    else:
                        console.print("No images found.")

            elif action == "export":
                if not document_id:
                    console.print("❌ Document ID required for export action")
                    raise typer.Exit(1) from None

                try:
                    doc_uuid = uuid.UUID(document_id)
                except ValueError:
                    console.print(f"❌ Invalid document ID: {document_id}")
                    raise typer.Exit(1) from None

                # Get document and images
                document = await db_manager.get_document_by_id(doc_uuid)
                if not document:
                    console.print(f"❌ Document not found: {document_id}")
                    raise typer.Exit(1) from None

                images = await db_manager.get_document_images(doc_uuid)
                if not images:
                    console.print("No images to export for this document.")
                    return

                # Create output directory
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)

                # Export images
                exported_count = 0
                for image in images:
                    try:
                        source_path = await image_storage.get_image_path(doc_uuid, image.image_path)
                        if source_path.exists():
                            target_path = output_path / image.filename
                            shutil.copy2(source_path, target_path)
                            exported_count += 1
                        else:
                            console.print(f"⚠️  Image file not found: {image.filename}")
                    except Exception as e:
                        console.print(f"❌ Failed to export {image.filename}: {e}")

                console.print(f"✅ Exported {exported_count}/{len(images)} images to {output_path}")

            elif action == "cleanup":
                # Cleanup orphaned images
                console.print("🧹 Cleaning up orphaned images...")
                # This would require implementing orphan detection logic
                console.print("Cleanup functionality not yet implemented.")

            elif action == "stats":
                # Show storage statistics
                stats = image_storage.get_storage_stats()
                console.print("\n📊 Image Storage Statistics")
                console.print(f"Base path: {stats['base_path']}")
                console.print(f"Total files: {stats['total_files']}")
                console.print(f"Total size: {stats['total_size_mb']:.2f} MB")

                # Get database stats
                picture_count = len(await db_manager.get_images_by_type(ImageType.PICTURE, limit=1000))
                table_count = len(await db_manager.get_images_by_type(ImageType.TABLE, limit=1000))

                console.print(f"Pictures in DB: {picture_count}")
                console.print(f"Tables in DB: {table_count}")

            else:
                console.print(f"❌ Unknown action: {action}")
                console.print("Available actions: list, export, cleanup, stats")
                raise typer.Exit(1) from None

        except Exception as e:
            console.print(f"❌ Error: {e}")
            raise typer.Exit(1) from None
        finally:
            await db_manager.close()

    asyncio.run(_images())


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
