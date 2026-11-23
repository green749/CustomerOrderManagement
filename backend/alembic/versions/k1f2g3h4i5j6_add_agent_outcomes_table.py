"""add_agent_outcomes_table

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-11-16 13:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'k1f2g3h4i5j6'
down_revision: Union[str, None] = 'j0e1f2g3h4i5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'agent_outcomes' not in existing_tables:
        op.create_table(
            'agent_outcomes',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('customer_order_id', sa.String(50), nullable=False),
            sa.Column('proposal_id', sa.Integer(), sa.ForeignKey('commitment_proposals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('promised_date', sa.Date(), nullable=False),
            sa.Column('actual_delivery_date', sa.Date(), nullable=False),
            sa.Column('variance_days', sa.Integer(), nullable=False),
            sa.Column('approval_type', sa.String(50), nullable=False),
            sa.Column('commitment_met', sa.Boolean(), nullable=False),
            sa.Column('delivered_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_agent_outcomes_customer_order_id', 'agent_outcomes', ['customer_order_id'])
        op.create_index('ix_agent_outcomes_proposal_id', 'agent_outcomes', ['proposal_id'])
        op.create_index('ix_agent_outcomes_promised_date', 'agent_outcomes', ['promised_date'])
        op.create_index('ix_agent_outcomes_actual_delivery_date', 'agent_outcomes', ['actual_delivery_date'])
        op.create_index('ix_agent_outcomes_approval_type', 'agent_outcomes', ['approval_type'])
        op.create_index('ix_agent_outcomes_commitment_met', 'agent_outcomes', ['commitment_met'])
        op.create_index('ix_agent_outcomes_created_at', 'agent_outcomes', ['created_at'])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'agent_outcomes' in existing_tables:
        op.drop_table('agent_outcomes')
