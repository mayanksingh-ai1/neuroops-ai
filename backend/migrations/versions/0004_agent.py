"""Persist bounded agent runs and their execution timeline."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('agent_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(64), nullable=False),
        sa.Column('task', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('expires_at', sa.Float(), nullable=False),
        sa.Column('error_code', sa.String(80)), sa.Column('result', sa.JSON()),
        sa.CheckConstraint("status IN ('queued','running','completed','failed','cancelled','timed_out')", name='ck_agent_run_status'))
    op.create_index('ix_agent_runs_workspace_id', 'agent_runs', ['workspace_id'])
    op.create_table('agent_steps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('agent_runs.id'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('tool', sa.String(40), nullable=False), sa.Column('arguments', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('output', sa.JSON()), sa.Column('error_code', sa.String(80)),
        sa.UniqueConstraint('run_id', 'position', name='uq_agent_step_position'),
        sa.CheckConstraint("status IN ('pending','running','completed','failed','cancelled','timed_out')", name='ck_agent_step_status'))
    op.create_index('ix_agent_steps_run_id', 'agent_steps', ['run_id'])


def downgrade():
    op.drop_table('agent_steps')
    op.drop_table('agent_runs')
