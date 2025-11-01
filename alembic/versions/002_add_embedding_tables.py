"""Add embedding tables for multimodal RAG

Revision ID: 002_add_embedding_tables
Revises: 001_add_document_images
Create Date: 2025-01-19 15:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "002_add_embedding_tables"
down_revision = "001_add_document_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add embedding tables and pgvector extension."""

    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create text_embeddings table
    op.create_table(
        "text_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "chunk_text",
            sa.Text(),
            nullable=False,
            comment="Text content of the chunk",
        ),
        sa.Column(
            "embedding",
            sa.Text(),  # Will be created as vector(1024) via raw SQL
            nullable=False,
            comment="1024-dimensional embedding vector from Jina CLIP v2",
        ),
        sa.Column(
            "page_number",
            sa.Integer(),
            nullable=True,
            comment="Page number where this chunk appears",
        ),
        sa.Column(
            "bbox_coordinates",
            sa.JSON(),
            nullable=True,
            comment="Bounding box coordinates {x, y, width, height}",
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
            comment="Order of this chunk within the document",
        ),
        sa.Column(
            "token_count",
            sa.Integer(),
            nullable=True,
            comment="Number of tokens in the chunk",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create image_embeddings table
    op.create_table(
        "image_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_image_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "embedding",
            sa.Text(),  # Will be created as vector(1024) via raw SQL
            nullable=False,
            comment="1024-dimensional embedding vector from Jina CLIP v2",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional description or caption for the image",
        ),
        sa.Column(
            "ocr_text",
            sa.Text(),
            nullable=True,
            comment="OCR extracted text for better retrieval",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_image_id"], ["document_images.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Convert embedding columns to proper vector type and create vector indexes
    op.execute(
        "ALTER TABLE text_embeddings ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)"
    )
    op.execute(
        "ALTER TABLE image_embeddings ALTER COLUMN embedding TYPE vector(1024) USING embedding::vector(1024)"
    )

    # Create vector similarity indexes using IVFFlat
    op.execute("""
        CREATE INDEX ix_text_embeddings_embedding_cosine
        ON text_embeddings USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    op.execute("""
        CREATE INDEX ix_image_embeddings_embedding_cosine
        ON image_embeddings USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Create indexes for text_embeddings
    op.create_index(
        op.f("ix_text_embeddings_id"),
        "text_embeddings",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_text_embeddings_document_id"),
        "text_embeddings",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_text_embeddings_page_number"),
        "text_embeddings",
        ["page_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_text_embeddings_created_at"),
        "text_embeddings",
        ["created_at"],
        unique=False,
    )

    # Create indexes for image_embeddings
    op.create_index(
        op.f("ix_image_embeddings_id"),
        "image_embeddings",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_image_embeddings_document_image_id"),
        "image_embeddings",
        ["document_image_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_image_embeddings_created_at"),
        "image_embeddings",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove embedding tables and indexes."""

    # Drop vector similarity indexes
    op.execute("DROP INDEX IF EXISTS ix_image_embeddings_embedding_cosine")
    op.execute("DROP INDEX IF EXISTS ix_text_embeddings_embedding_cosine")

    # Drop indexes for image_embeddings
    op.drop_index(op.f("ix_image_embeddings_created_at"), table_name="image_embeddings")
    op.drop_index(
        op.f("ix_image_embeddings_document_image_id"), table_name="image_embeddings"
    )
    op.drop_index(op.f("ix_image_embeddings_id"), table_name="image_embeddings")

    # Drop indexes for text_embeddings
    op.drop_index(op.f("ix_text_embeddings_created_at"), table_name="text_embeddings")
    op.drop_index(op.f("ix_text_embeddings_page_number"), table_name="text_embeddings")
    op.drop_index(op.f("ix_text_embeddings_document_id"), table_name="text_embeddings")
    op.drop_index(op.f("ix_text_embeddings_id"), table_name="text_embeddings")

    # Drop tables
    op.drop_table("image_embeddings")
    op.drop_table("text_embeddings")

    # Note: We don't drop the vector extension as other applications might be using it
    # op.execute("DROP EXTENSION IF EXISTS vector")
