"""add_agent_actions_table

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-11-16 13:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'j0e1f2g3h4i5'
down_revision: Union[str, None] = 'i9d0e1f2g3h4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'agent_actions' not in existing_tables:
        op.create_table(
            'agent_actions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('alert_id', sa.Integer(), sa.ForeignKey('risk_alerts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('customer_order_id', sa.String(50), nullable=False),
            sa.Column('action_type', sa.String(50), nullable=False),
            sa.Column('parameters', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='PROPOSED'),
            sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('proposed_by', sa.String(50), nullable=False, server_default='agent3-monitoring'),
            sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('executed_at', sa.DateTime(), nullable=True),
            sa.Column('result', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_agent_actions_alert_id', 'agent_actions', ['alert_id'])
        op.create_index('ix_agent_actions_customer_order_id', 'agent_actions', ['customer_order_id'])
        op.create_index('ix_agent_actions_action_type', 'agent_actions', ['action_type'])
        op.create_index('ix_agent_actions_status', 'agent_actions', ['status'])
        op.create_index('ix_agent_actions_created_at', 'agent_actions', ['created_at'])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'agent_actions' in existing_tables:
        op.drop_table('agent_actions')
