"""initial schema: documents, document_versions, chunks, ingestion_jobs

Revision ID: d4b92ed060b2
Revises: 
Create Date: 2026-08-13 04:49:58.048879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'd4b92ed060b2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('documents',
                    sa.Column('id', sa.UUID(), nullable=False),
                    sa.Column('title', sa.String(length=500), nullable=False),
                    sa.Column('source', sa.String(length=255), nullable=False),
                    sa.Column('document_type', sa.String(
                        length=100), nullable=False),
                    sa.Column('owner', sa.String(length=255), nullable=True),
                    sa.Column('status', sa.Enum('ACTIVE', 'ARCHIVED', 'DELETED',
                                                name='documentstatus', native_enum=False), nullable=False),
                    sa.Column('active_version_id', sa.UUID(), nullable=True),
                    sa.Column('metadata', sa.JSON(), nullable=True),
                    sa.Column('created_at', sa.DateTime(timezone=True),
                              server_default=sa.text('now()'), nullable=True),
                    sa.Column('updated_at', sa.DateTime(timezone=True),
                              server_default=sa.text('now()'), nullable=True),
                    sa.Column('deleted_at', sa.DateTime(
                        timezone=True), nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    # NOTE: active_version_id's FK is added below via op.create_foreign_key,
                    # AFTER document_versions exists — see comment there for why.
                    )

    op.create_table('document_versions',
                    sa.Column('id', sa.UUID(), nullable=False),
                    sa.Column('document_id', sa.UUID(), nullable=False),
                    sa.Column('version', sa.Integer(), nullable=False),
                    sa.Column('is_active', sa.Boolean(), nullable=False),
                    sa.Column('storage_path', sa.String(
                        length=500), nullable=False),
                    sa.Column('checksum', sa.String(
                        length=64), nullable=False),
                    sa.Column('file_name', sa.String(
                        length=255), nullable=False),
                    sa.Column('mime_type', sa.String(
                        length=100), nullable=True),
                    sa.Column('file_size', sa.BigInteger(), nullable=True),
                    sa.Column('embedding_model', sa.String(
                        length=100), nullable=True),
                    sa.Column('embedding_dimension',
                              sa.Integer(), nullable=True),
                    sa.Column('processing_status', sa.Enum('UPLOADING', 'QUEUED', 'PROCESSING',
                                                           'READY', 'FAILED', name='processingstatus', native_enum=False), nullable=False),
                    sa.Column('chunk_count', sa.Integer(), nullable=False),
                    sa.Column('created_at', sa.DateTime(timezone=True),
                              server_default=sa.text('now()'), nullable=True),
                    sa.Column('updated_at', sa.DateTime(timezone=True),
                              server_default=sa.text('now()'), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['document_id'], ['documents.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('document_id', 'version',
                                        name='uq_document_version')
                    )

    # documents.active_version_id -> document_versions.id, added here (not inline
    # above) because documents and document_versions reference each other:
    # document_versions.document_id needs documents to exist first, and
    # documents.active_version_id needs document_versions to exist first.
    # This ALTER TABLE step runs only once both tables are already created.
    op.create_foreign_key(
        'fk_document_active_version',
        'documents', 'document_versions',
        ['active_version_id'], ['id']
    )

    op.create_table('chunks',
                    sa.Column('id', sa.UUID(), nullable=False),
                    sa.Column('document_version_id',
                              sa.UUID(), nullable=False),
                    sa.Column('chunk_index', sa.Integer(), nullable=False),
                    sa.Column('page_number', sa.Integer(), nullable=True),
                    sa.Column('text', sa.Text(), nullable=False),
                    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(
                        dim=1536), nullable=False),
                    sa.ForeignKeyConstraint(['document_version_id'], [
                        'document_versions.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('document_version_id',
                                        'chunk_index', name='uq_chunk_version_index')
                    )
    op.create_index('idx_chunk_embedding', 'chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={
                    'embedding': 'vector_cosine_ops'}, postgresql_with={'m': 16, 'ef_construction': 64})
    op.create_index('idx_chunk_version_page', 'chunks', [
                    'document_version_id', 'page_number'], unique=False)

    op.create_table('ingestion_jobs',
                    sa.Column('id', sa.UUID(), nullable=False),
                    sa.Column('document_version_id',
                              sa.UUID(), nullable=False),
                    sa.Column('status', sa.Enum('PENDING', 'QUEUED', 'PROCESSING', 'EMBEDDING', 'GRAPH_BUILD',
                                                'COMPLETED', 'FAILED', name='jobstatus', native_enum=False), nullable=False),
                    sa.Column('progress', sa.Integer(), nullable=False),
                    sa.Column('retry_count', sa.Integer(), nullable=False),
                    sa.Column('worker', sa.String(length=255), nullable=True),
                    sa.Column('error_message', sa.Text(), nullable=True),
                    sa.Column('execution_id', sa.UUID(), nullable=False),
                    sa.Column('started_at', sa.DateTime(
                        timezone=True), nullable=True),
                    sa.Column('completed_at', sa.DateTime(
                        timezone=True), nullable=True),
                    sa.Column('created_at', sa.DateTime(timezone=True),
                              server_default=sa.text('now()'), nullable=True),
                    sa.ForeignKeyConstraint(['document_version_id'], [
                        'document_versions.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ingestion_jobs')
    op.drop_index('idx_chunk_version_page', table_name='chunks')
    op.drop_index('idx_chunk_embedding', table_name='chunks')
    op.drop_table('chunks')
    # drop the deferred FK before dropping document_versions, or the drop
    # fails since documents.active_version_id still references it
    op.drop_constraint('fk_document_active_version',
                       'documents', type_='foreignkey')
    op.drop_table('document_versions')
    op.drop_table('documents')
