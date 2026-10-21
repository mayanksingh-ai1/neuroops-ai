"""Add separate analysis history without changing original complaints."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'complaint_analyses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('complaint_id', sa.String(64), sa.ForeignKey('complaints.complaint_id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('category', sa.String(80)),
        sa.Column('sentiment', sa.String(10)),
        sa.Column('priority', sa.String(10)),
        sa.Column('error_code', sa.String(40)),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_complaint_analyses_complaint_id', 'complaint_analyses', ['complaint_id'])


def downgrade():
    op.drop_table('complaint_analyses')
