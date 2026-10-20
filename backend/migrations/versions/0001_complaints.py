"""Create complaint storage and indexes. No sample records are seeded."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('complaints',
        sa.Column('complaint_id', sa.String(64), primary_key=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('category', sa.String(80), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('priority', sa.String(10), nullable=False),
        sa.Column('channel', sa.String(40), nullable=False),
        sa.Column('received_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'resolved')", name='ck_complaint_status'),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name='ck_complaint_priority'))
    op.create_index('ix_complaints_category', 'complaints', ['category'])
    op.create_index('ix_complaints_status', 'complaints', ['status'])
    op.create_index('ix_complaints_received_date', 'complaints', ['received_date'])


def downgrade():
    op.drop_table('complaints')
