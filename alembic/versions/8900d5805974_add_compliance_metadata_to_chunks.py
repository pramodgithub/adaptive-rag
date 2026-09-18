"""add compliance metadata to chunks

Revision ID: 8900d5805974
Revises: c4af8c2c409a
Create Date: 2026-09-17 11:07:03.086106

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.

revision: str = "8900d5805974"
down_revision: Union[str, Sequence[str], None] = "c4af8c2c409a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("page_start", sa.Integer(), nullable=True),
    )

    op.add_column(
        "chunks",
        sa.Column("page_end", sa.Integer(), nullable=True),
    )

    op.add_column(
        "chunks",
        sa.Column(
            "section_path",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "chunks",
        sa.Column(
            "structure_type",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "chunks",
        sa.Column(
            "identifier",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "chunks",
        sa.Column(
            "parent_identifier",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "chunks",
        sa.Column(
            "element_indexes",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "chunks",
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.create_index(
        "idx_chunk_version_page_range",
        "chunks",
        ["document_version_id", "page_start", "page_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_chunk_version_page_range",
        table_name="chunks",
    )

    op.drop_column("chunks", "metadata")
    op.drop_column("chunks", "element_indexes")
    op.drop_column("chunks", "parent_identifier")
    op.drop_column("chunks", "identifier")
    op.drop_column("chunks", "structure_type")
    op.drop_column("chunks", "section_path")
    op.drop_column("chunks", "page_end")
    op.drop_column("chunks", "page_start")
