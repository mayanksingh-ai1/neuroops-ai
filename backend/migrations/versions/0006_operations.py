"""Running evaluation states and indexes for common workspace/history queries."""
from alembic import op
import sqlalchemy as sa
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('evaluations') as batch:
        batch.drop_constraint('ck_evaluation_status', type_='check')
        batch.create_check_constraint('ck_evaluation_status', "status IN ('running','completed','failed')")
        batch.add_column(sa.Column('expires_at', sa.Float(), nullable=True))
    for table, columns in (
        ('agent_runs', ['workspace_id', 'created_at']), ('agent_runs', ['status', 'expires_at']),
        ('evaluation_cases', ['workspace_id', 'created_at']), ('evaluations', ['case_id', 'created_at']),
        ('evaluations', ['status', 'expires_at']), ('evaluation_reviews', ['evaluation_id', 'created_at']),
        ('knowledge_documents', ['workspace_id', 'created_at']), ('complaint_analyses', ['complaint_id', 'created_at'])):
        op.create_index('ix_' + table + '_' + '_'.join(columns), table, columns)


def downgrade():
    op.execute("UPDATE evaluations SET status='failed', error_code='interrupted_evaluation' WHERE status='running'")
    for table, columns in (
        ('agent_runs', ['workspace_id', 'created_at']), ('agent_runs', ['status', 'expires_at']),
        ('evaluation_cases', ['workspace_id', 'created_at']), ('evaluations', ['case_id', 'created_at']),
        ('evaluations', ['status', 'expires_at']), ('evaluation_reviews', ['evaluation_id', 'created_at']),
        ('knowledge_documents', ['workspace_id', 'created_at']), ('complaint_analyses', ['complaint_id', 'created_at'])):
        op.drop_index('ix_' + table + '_' + '_'.join(columns), table_name=table)
    with op.batch_alter_table('evaluations') as batch:
        batch.drop_column('expires_at')
        batch.drop_constraint('ck_evaluation_status', type_='check')
        batch.create_check_constraint('ck_evaluation_status', "status IN ('completed','failed')")
