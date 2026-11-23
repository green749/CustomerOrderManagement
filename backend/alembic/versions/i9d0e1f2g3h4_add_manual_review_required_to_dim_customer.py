"""add_manual_review_required_to_dim_customer

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-11-16 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'i9d0e1f2g3h4'
down_revision: Union[str, None] = 'h8c9d0e1f2g3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'dim_customer' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('dim_customer')]
        if 'manual_review_required' not in existing_cols:
            op.add_column('dim_customer', sa.Column('manual_review_required', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'dim_customer' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('dim_customer')]
        if 'manual_review_required' in existing_cols:
            op.drop_column('dim_customer', 'manual_review_required')
