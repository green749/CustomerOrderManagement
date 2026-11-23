"""add_agent_columns_to_order_assessments

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-11-16 12:43:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'h8c9d0e1f2g3'
down_revision: Union[str, None] = 'g7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'order_assessments' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('order_assessments')]
        if 'agent_reasoning' not in existing_cols:
            op.add_column('order_assessments', sa.Column('agent_reasoning', sa.JSON(), nullable=True))
        if 'agent_output' not in existing_cols:
            op.add_column('order_assessments', sa.Column('agent_output', sa.JSON(), nullable=True))
        if 'agent_disagreement' not in existing_cols:
            op.add_column('order_assessments', sa.Column('agent_disagreement', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'order_assessments' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('order_assessments')]
        if 'agent_disagreement' in existing_cols:
            op.drop_column('order_assessments', 'agent_disagreement')
        if 'agent_output' in existing_cols:
            op.drop_column('order_assessments', 'agent_output')
        if 'agent_reasoning' in existing_cols:
            op.drop_column('order_assessments', 'agent_reasoning')
