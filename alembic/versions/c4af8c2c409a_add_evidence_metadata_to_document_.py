"""add evidence metadata to document versions

Revision ID: c4af8c2c409a
Revises: 978ebc61aa77
Create Date: 2026-09-03 17:14:39.029913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'c4af8c2c409a'
down_revision: Union[str, Sequence[str], None] = '978ebc61aa77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_versions",
        sa.Column("source_type", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("issuer", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("jurisdiction", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("authority_level", sa.String(length=50), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("publication_date", sa.Date(), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("effective_date", sa.Date(), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("expiration_date", sa.Date(), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("verification_status", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_versions", "verification_status")
    op.drop_column("document_versions", "expiration_date")
    op.drop_column("document_versions", "effective_date")
    op.drop_column("document_versions", "publication_date")
    op.drop_column("document_versions", "authority_level")
    op.drop_column("document_versions", "jurisdiction")
    op.drop_column("document_versions", "issuer")
    op.drop_column("document_versions", "source_type")
