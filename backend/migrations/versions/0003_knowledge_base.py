"""Add isolated knowledge storage; existing complaint tables are untouched."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('knowledge_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(180), nullable=False),
        sa.Column('file_type', sa.String(10), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_code', sa.String(50)),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('source_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'fingerprint', name='uq_kb_workspace_fingerprint'),
        sa.CheckConstraint("status IN ('processing', 'ready', 'failed')", name='ck_kb_status'))
    op.create_index('ix_knowledge_documents_workspace_id', 'knowledge_documents', ['workspace_id'])
    op.create_table('knowledge_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('knowledge_documents.id'), nullable=False),
        sa.Column('page_number', sa.Integer()),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('passage', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_kb_document_chunk'))
    op.create_index('ix_knowledge_chunks_document_id', 'knowledge_chunks', ['document_id'])


def downgrade():
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_documents')
