"""add_commitment_proposals_and_audit_log

Revision ID: c3dcf731cf90
Revises: bba26adb5eca
Create Date: 2026-11-12 12:38:40.701939

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3dcf731cf90'
down_revision: Union[str, None] = 'bba26adb5eca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users.customer_scope
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()
    user_cols = [c['name'] for c in insp.get_columns('users')]

    if 'customer_scope' not in user_cols:
        op.add_column('users', sa.Column('customer_scope', sa.JSON(), nullable=True))

    # 2. commitment_proposals
    if 'commitment_proposals' not in existing_tables:
        op.create_table(
            'commitment_proposals',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('customer_order_id', sa.String(length=50), nullable=False),
            sa.Column('proposed_date', sa.Date(), nullable=False),
            sa.Column('recommended_by', sa.String(length=50), nullable=False, server_default='agent'),
            sa.Column('reasons', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
            sa.Column('created_by', sa.Integer(), nullable=False),
            sa.Column('decided_by', sa.Integer(), nullable=True),
            sa.Column('decided_at', sa.DateTime(), nullable=True),
            sa.Column('decision_note', sa.Text(), nullable=True),
            sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_order_revision', 'commitment_proposals', ['customer_order_id', 'revision'], unique=False)
        op.create_index('idx_proposal_status', 'commitment_proposals', ['status'], unique=False)

    # 3. audit_log
    if 'audit_log' not in existing_tables:
        op.create_table(
            'audit_log',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('entity', sa.String(length=100), nullable=False),
            sa.Column('entity_id', sa.String(length=100), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)
        op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)
        op.create_index(op.f('ix_audit_log_entity'), 'audit_log', ['entity'], unique=False)
        op.create_index(op.f('ix_audit_log_user_id'), 'audit_log', ['user_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()
    user_cols = [c['name'] for c in insp.get_columns('users')]

    if 'audit_log' in existing_tables:
        op.drop_table('audit_log')
    if 'commitment_proposals' in existing_tables:
        op.drop_table('commitment_proposals')
    if 'customer_scope' in user_cols:
        op.drop_column('users', 'customer_scope')
