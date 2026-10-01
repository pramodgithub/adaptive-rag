"""add chunk semantic entities

Revision ID: c63985b9550a
Revises: 8900d5805974
Create Date: 2026-09-19 07:22:50.506124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'c63985b9550a'
down_revision: Union[str, Sequence[str], None] = '8900d5805974'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunk_semantic_entities",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "framework",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "identifier",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "parent_identifier",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "validation_status",
            sa.String(length=50),
            nullable=False,
            server_default="review",
        ),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            server_default="llm",
        ),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chunk_id",
            "framework",
            "identifier",
            name="uq_semantic_entity_chunk_identifier",
        ),
    )

    op.create_index(
        "idx_semantic_entity_chunk",
        "chunk_semantic_entities",
        ["chunk_id"],
    )

    op.create_index(
        "idx_semantic_entity_framework_identifier",
        "chunk_semantic_entities",
        ["framework", "identifier"],
    )

    op.create_index(
        "idx_semantic_entity_validation_status",
        "chunk_semantic_entities",
        ["validation_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_semantic_entity_validation_status",
        table_name="chunk_semantic_entities",
    )

    op.drop_index(
        "idx_semantic_entity_framework_identifier",
        table_name="chunk_semantic_entities",
    )

    op.drop_index(
        "idx_semantic_entity_chunk",
        table_name="chunk_semantic_entities",
    )

    op.drop_table("chunk_semantic_entities")
