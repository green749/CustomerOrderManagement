"""email_notifications_and_rbac

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-13 13:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Add columns to users
    if 'users' in existing_tables:
        user_cols = [c['name'] for c in insp.get_columns('users')]
        if 'department' not in user_cols:
            op.add_column('users', sa.Column('department', sa.String(length=50), nullable=True))
        if 'can_approve_commitments' not in user_cols:
            op.add_column('users', sa.Column('can_approve_commitments', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # 2. Add columns to risk_alerts
    if 'risk_alerts' in existing_tables:
        alert_cols = [c['name'] for c in insp.get_columns('risk_alerts')]
        if 'customer_communicated' not in alert_cols:
            op.add_column('risk_alerts', sa.Column('customer_communicated', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        if 'customer_communication_notes' not in alert_cols:
            op.add_column('risk_alerts', sa.Column('customer_communication_notes', sa.Text(), nullable=True))
        if 'customer_communicated_at' not in alert_cols:
            op.add_column('risk_alerts', sa.Column('customer_communicated_at', sa.DateTime(), nullable=True))
        if 'customer_communicated_by' not in alert_cols:
            op.add_column('risk_alerts', sa.Column('customer_communicated_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    # 3. Add columns to email_notification_logs
    if 'email_notification_logs' in existing_tables:
        log_cols = [c['name'] for c in insp.get_columns('email_notification_logs')]
        if 'recipient_category' not in log_cols:
            op.add_column('email_notification_logs', sa.Column('recipient_category', sa.String(length=50), nullable=False, server_default='OPERATIONAL'))
        if 'notification_type' not in log_cols:
            op.add_column('email_notification_logs', sa.Column('notification_type', sa.String(length=50), nullable=False, server_default='ACTION_REQUIRED'))
        if 'provider_message_id' not in log_cols:
            op.add_column('email_notification_logs', sa.Column('provider_message_id', sa.String(length=255), nullable=True))

    # 4. Create department_mappings table
    if 'department_mappings' not in existing_tables:
        op.create_table(
            'department_mappings',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('issue_category', sa.String(length=100), unique=True, nullable=False),
            sa.Column('issue_label', sa.String(length=150), nullable=False),
            sa.Column('responsible_department', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'department_mappings' in existing_tables:
        op.drop_table('department_mappings')

    if 'email_notification_logs' in existing_tables:
        log_cols = [c['name'] for c in insp.get_columns('email_notification_logs')]
        if 'provider_message_id' in log_cols:
            op.drop_column('email_notification_logs', 'provider_message_id')
        if 'notification_type' in log_cols:
            op.drop_column('email_notification_logs', 'notification_type')
        if 'recipient_category' in log_cols:
            op.drop_column('email_notification_logs', 'recipient_category')

    if 'risk_alerts' in existing_tables:
        alert_cols = [c['name'] for c in insp.get_columns('risk_alerts')]
        if 'customer_communicated_by' in alert_cols:
            op.drop_column('risk_alerts', 'customer_communicated_by')
        if 'customer_communicated_at' in alert_cols:
            op.drop_column('risk_alerts', 'customer_communicated_at')
        if 'customer_communication_notes' in alert_cols:
            op.drop_column('risk_alerts', 'customer_communication_notes')
        if 'customer_communicated' in alert_cols:
            op.drop_column('risk_alerts', 'customer_communicated')

    if 'users' in existing_tables:
        user_cols = [c['name'] for c in insp.get_columns('users')]
        if 'can_approve_commitments' in user_cols:
            op.drop_column('users', 'can_approve_commitments')
        if 'department' in user_cols:
            op.drop_column('users', 'department')
