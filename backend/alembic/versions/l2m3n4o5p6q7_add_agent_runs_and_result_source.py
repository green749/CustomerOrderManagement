"""add_agent_runs_and_result_source

Revision ID: l2m3n4o5p6q7
Revises: k1f2g3h4i5j6
Create Date: 2026-11-17 12:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1f2g3h4i5j6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Create agent_runs table
    if 'agent_runs' not in existing_tables:
        op.create_table(
            'agent_runs',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('agent_name', sa.String(50), nullable=False),
            sa.Column('customer_order_id', sa.String(50), nullable=False),
            sa.Column('assessment_id', sa.String(50), nullable=True),
            sa.Column('alert_id', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False, server_default='domo_ai'),
            sa.Column('steps', sa.JSON(), nullable=True),
            sa.Column('final_output', sa.JSON(), nullable=True),
            sa.Column('llm_calls', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_agent_runs_agent_name', 'agent_runs', ['agent_name'])
        op.create_index('ix_agent_runs_customer_order_id', 'agent_runs', ['customer_order_id'])
        op.create_index('ix_agent_runs_assessment_id', 'agent_runs', ['assessment_id'])
        op.create_index('ix_agent_runs_alert_id', 'agent_runs', ['alert_id'])
        op.create_index('ix_agent_runs_status', 'agent_runs', ['status'])
        op.create_index('ix_agent_runs_created_at', 'agent_runs', ['created_at'])

    # 2. Add columns to order_assessments
    if 'order_assessments' in existing_tables:
        oa_cols = [c['name'] for c in insp.get_columns('order_assessments')]
        if 'result_source' not in oa_cols:
            op.add_column('order_assessments', sa.Column('result_source', sa.String(20), nullable=False, server_default='RULES_FALLBACK'))
        if 'revised_estimated_date' not in oa_cols:
            op.add_column('order_assessments', sa.Column('revised_estimated_date', sa.Date(), nullable=True))
        if 'delay_days' not in oa_cols:
            op.add_column('order_assessments', sa.Column('delay_days', sa.Integer(), nullable=True))
        if 'verdict' not in oa_cols:
            op.add_column('order_assessments', sa.Column('verdict', sa.String(20), nullable=True))

    # 3. Add columns to risk_alerts
    if 'risk_alerts' in existing_tables:
        ra_cols = [c['name'] for c in insp.get_columns('risk_alerts')]
        if 'result_source' not in ra_cols:
            op.add_column('risk_alerts', sa.Column('result_source', sa.String(20), nullable=False, server_default='RULES_FALLBACK'))

    # 4. Add columns to commitment_proposals
    if 'commitment_proposals' in existing_tables:
        cp_cols = [c['name'] for c in insp.get_columns('commitment_proposals')]
        if 'revised_estimated_date' not in cp_cols:
            op.add_column('commitment_proposals', sa.Column('revised_estimated_date', sa.Date(), nullable=True))
        if 'delay_days' not in cp_cols:
            op.add_column('commitment_proposals', sa.Column('delay_days', sa.Integer(), nullable=True))
        if 'verdict' not in cp_cols:
            op.add_column('commitment_proposals', sa.Column('verdict', sa.String(20), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'agent_runs' in existing_tables:
        op.drop_table('agent_runs')

    if 'order_assessments' in existing_tables:
        oa_cols = [c['name'] for c in insp.get_columns('order_assessments')]
        if 'verdict' in oa_cols:
            op.drop_column('order_assessments', 'verdict')
        if 'delay_days' in oa_cols:
            op.drop_column('order_assessments', 'delay_days')
        if 'revised_estimated_date' in oa_cols:
            op.drop_column('order_assessments', 'revised_estimated_date')
        if 'result_source' in oa_cols:
            op.drop_column('order_assessments', 'result_source')

    if 'risk_alerts' in existing_tables:
        ra_cols = [c['name'] for c in insp.get_columns('risk_alerts')]
        if 'result_source' in ra_cols:
            op.drop_column('risk_alerts', 'result_source')

    if 'commitment_proposals' in existing_tables:
        cp_cols = [c['name'] for c in insp.get_columns('commitment_proposals')]
        if 'verdict' in cp_cols:
            op.drop_column('commitment_proposals', 'verdict')
        if 'delay_days' in cp_cols:
            op.drop_column('commitment_proposals', 'delay_days')
        if 'revised_estimated_date' in cp_cols:
            op.drop_column('commitment_proposals', 'revised_estimated_date')
