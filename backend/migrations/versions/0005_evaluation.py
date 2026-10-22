"""Separate evaluation cases, immutable results, reviews, and comparisons."""
import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('evaluation_cases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(64), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('dataset', sa.String(80), nullable=False),
        sa.Column('model', sa.String(120), nullable=False),
        sa.Column('provider', sa.String(80), nullable=False),
        sa.Column('question', sa.Text(), nullable=False), sa.Column('response', sa.Text(), nullable=False),
        sa.Column('reference', sa.Text()), sa.Column('context', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'fingerprint', name='uq_eval_case_fingerprint'))
    for field in ('workspace_id', 'dataset', 'model'):
        op.create_index('ix_evaluation_cases_' + field, 'evaluation_cases', [field])
    op.create_table('evaluations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('case_id', sa.String(36), sa.ForeignKey('evaluation_cases.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('deterministic', sa.JSON(), nullable=False), sa.Column('judged', sa.JSON(), nullable=False),
        sa.Column('rubric', sa.JSON(), nullable=False), sa.Column('evaluator', sa.JSON(), nullable=False),
        sa.Column('error_code', sa.String(80)), sa.Column('created_at', sa.Float(), nullable=False),
        sa.CheckConstraint("status IN ('completed','failed')", name='ck_evaluation_status'))
    op.create_index('ix_evaluations_case_id', 'evaluations', ['case_id'])
    op.create_table('evaluation_reviews',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('evaluation_id', sa.String(36), sa.ForeignKey('evaluations.id'), nullable=False),
        sa.Column('reviewer_id', sa.String(80), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False), sa.Column('feedback', sa.Text(), nullable=False),
        sa.Column('corrections', sa.JSON(), nullable=False), sa.Column('created_at', sa.Float(), nullable=False),
        sa.CheckConstraint("decision IN ('approve','reject','correct')", name='ck_evaluation_review_decision'))
    op.create_index('ix_evaluation_reviews_evaluation_id', 'evaluation_reviews', ['evaluation_id'])
    op.create_table('evaluation_comparisons',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('workspace_id', sa.String(64), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False), sa.Column('created_at', sa.Float(), nullable=False))
    op.create_index('ix_evaluation_comparisons_workspace_id', 'evaluation_comparisons', ['workspace_id'])


def downgrade():
    op.drop_table('evaluation_comparisons')
    op.drop_table('evaluation_reviews')
    op.drop_table('evaluations')
    op.drop_table('evaluation_cases')
