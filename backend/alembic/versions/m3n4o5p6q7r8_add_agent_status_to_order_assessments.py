"""add_agent_status_to_order_assessments

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-11-17 19:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'm3n4o5p6q7r8'
down_revision: Union[str, None] = 'l2m3n4o5p6q7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'order_assessments' in existing_tables:
        oa_cols = [c['name'] for c in insp.get_columns('order_assessments')]
        if 'agent_status' not in oa_cols:
            op.add_column(
                'order_assessments',
                sa.Column('agent_status', sa.String(50), nullable=True, server_default='rules_mode'),
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'order_assessments' in existing_tables:
        oa_cols = [c['name'] for c in insp.get_columns('order_assessments')]
        if 'agent_status' in oa_cols:
            op.drop_column('order_assessments', 'agent_status')
