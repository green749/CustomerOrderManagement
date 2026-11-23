"""scheduler_lease_and_hardening

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-12 21:58:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. scheduler_leases
    if 'scheduler_leases' not in existing_tables:
        op.create_table(
            'scheduler_leases',
            sa.Column('lease_name', sa.String(length=100), primary_key=True, nullable=False),
            sa.Column('holder_id', sa.String(length=150), nullable=True),
            sa.Column('acquired_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
            sa.Column('last_cycle_status', sa.String(length=50), nullable=True),
            sa.Column('last_cycle_summary', sa.Text(), nullable=True),
            sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        )
        op.create_index('idx_scheduler_lease_expiry', 'scheduler_leases', ['expires_at'])

    # 2. Add duration and timing columns to monitoring_execution_logs if not present
    if 'monitoring_execution_logs' in existing_tables:
        cols = [c['name'] for c in insp.get_columns('monitoring_execution_logs')]
        if 'started_at' not in cols:
            op.add_column('monitoring_execution_logs', sa.Column('started_at', sa.DateTime(), nullable=True))
        if 'duration_seconds' not in cols:
            op.add_column('monitoring_execution_logs', sa.Column('duration_seconds', sa.Float(), nullable=True))

    # 3. Add last_attempt_at to email_notification_logs if not present
    if 'email_notification_logs' in existing_tables:
        cols = [c['name'] for c in insp.get_columns('email_notification_logs')]
        if 'last_attempt_at' not in cols:
            op.add_column('email_notification_logs', sa.Column('last_attempt_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'scheduler_leases' in existing_tables:
        op.drop_table('scheduler_leases')

    if 'monitoring_execution_logs' in existing_tables:
        cols = [c['name'] for c in insp.get_columns('monitoring_execution_logs')]
        if 'duration_seconds' in cols:
            op.drop_column('monitoring_execution_logs', 'duration_seconds')
        if 'started_at' in cols:
            op.drop_column('monitoring_execution_logs', 'started_at')

    if 'email_notification_logs' in existing_tables:
        cols = [c['name'] for c in insp.get_columns('email_notification_logs')]
        if 'last_attempt_at' in cols:
            op.drop_column('email_notification_logs', 'last_attempt_at')

