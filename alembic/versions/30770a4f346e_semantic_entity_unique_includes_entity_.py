"""semantic entity unique includes entity type

Revision ID: 30770a4f346e
Revises: c63985b9550a
Create Date: 2026-11-27 07:29:11.158980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '30770a4f346e'
down_revision: Union[str, Sequence[str], None] = 'c63985b9550a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_semantic_entity_chunk_identifier", "chunk_semantic_entities", type_="unique")
    op.create_unique_constraint(
        "uq_semantic_entity_chunk_type_identifier",
        "chunk_semantic_entities",
        ["chunk_id", "framework", "entity_type", "identifier"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_semantic_entity_chunk_type_identifier", "chunk_semantic_entities", type_="unique")
    op.create_unique_constraint(
        "uq_semantic_entity_chunk_identifier",
        "chunk_semantic_entities",
        ["chunk_id", "framework", "identifier"],
    )