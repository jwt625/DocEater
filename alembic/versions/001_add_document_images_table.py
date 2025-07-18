"""Add document_images table

Revision ID: 001_add_document_images
Revises:
Create Date: 2025-01-19 12:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "001_add_document_images"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "document_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "image_path",
            sa.Text(),
            nullable=False,
            comment="Relative path from images root directory",
        ),
        sa.Column(
            "filename",
            sa.String(length=255),
            nullable=False,
            comment="Original extracted filename",
        ),
        sa.Column(
            "image_type",
            sa.String(length=20),
            nullable=False,
            comment="Type of image: picture, table, formula, etc.",
        ),
        sa.Column(
            "image_index",
            sa.Integer(),
            nullable=False,
            comment="Order/index within the document",
        ),
        sa.Column(
            "file_size",
            sa.BigInteger(),
            nullable=False,
            comment="Image file size in bytes",
        ),
        sa.Column(
            "width", sa.Integer(), nullable=True, comment="Image width in pixels"
        ),
        sa.Column(
            "height", sa.Integer(), nullable=True, comment="Image height in pixels"
        ),
        sa.Column(
            "format",
            sa.String(length=10),
            nullable=True,
            comment="Image format: PNG, JPEG, WEBP, etc.",
        ),
        sa.Column(
            "extraction_method",
            sa.String(length=50),
            nullable=True,
            comment="Method used for extraction",
        ),
        sa.Column(
            "quality_score",
            sa.Float(),
            nullable=True,
            comment="Optional quality assessment score",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_images_created_at"),
        "document_images",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_images_document_id"),
        "document_images",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_images_id"), "document_images", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_document_images_image_type"),
        "document_images",
        ["image_type"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_document_images_image_type"), table_name="document_images")
    op.drop_index(op.f("ix_document_images_id"), table_name="document_images")
    op.drop_index(op.f("ix_document_images_document_id"), table_name="document_images")
    op.drop_index(op.f("ix_document_images_created_at"), table_name="document_images")
    op.drop_table("document_images")
    # ### end Alembic commands ###
