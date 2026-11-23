"""three_agent_architecture_tables

Revision ID: d4e5f6a7b8c9
Revises: c3dcf731cf90
Create Date: 2026-11-12 21:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3dcf731cf90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. order_assessments
    if 'order_assessments' not in existing_tables:
        op.create_table(
            'order_assessments',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('assessment_id', sa.String(length=50), nullable=False),
            sa.Column('customer_id', sa.String(length=50), nullable=False),
            sa.Column('product_id', sa.String(length=50), nullable=False),
            sa.Column('order_qty', sa.Integer(), nullable=False),
            sa.Column('requested_delivery_date', sa.Date(), nullable=False),
            sa.Column('unit_price_inr', sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column('priority', sa.String(length=50), server_default='MEDIUM', nullable=False),
            sa.Column('channel', sa.String(length=50), server_default='EDI', nullable=False),
            sa.Column('ship_to', sa.String(length=255), nullable=True),
            sa.Column('product_config', sa.JSON(), nullable=True),
            sa.Column('packaging_req', sa.String(length=255), nullable=True),
            sa.Column('overall_status', sa.String(length=50), server_default='INSUFFICIENT_DATA', nullable=False),
            sa.Column('estimated_delivery_date', sa.Date(), nullable=True),
            sa.Column('days_variance', sa.Integer(), nullable=True),
            sa.Column('confidence_level', sa.String(length=50), server_default='MEDIUM', nullable=False),
            sa.Column('blockers_summary', sa.JSON(), nullable=True),
            sa.Column('corrective_actions_summary', sa.JSON(), nullable=True),
            sa.Column('missing_data', sa.JSON(), nullable=True),
            sa.Column('proposal_id', sa.Integer(), nullable=True),
            sa.Column('customer_order_id', sa.String(length=50), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
            sa.ForeignKeyConstraint(['proposal_id'], ['commitment_proposals.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_order_assessments_assessment_id'), 'order_assessments', ['assessment_id'], unique=True)
        op.create_index(op.f('ix_order_assessments_customer_id'), 'order_assessments', ['customer_id'], unique=False)
        op.create_index(op.f('ix_order_assessments_product_id'), 'order_assessments', ['product_id'], unique=False)
        op.create_index(op.f('ix_order_assessments_requested_delivery_date'), 'order_assessments', ['requested_delivery_date'], unique=False)
        op.create_index(op.f('ix_order_assessments_overall_status'), 'order_assessments', ['overall_status'], unique=False)
        op.create_index(op.f('ix_order_assessments_customer_order_id'), 'order_assessments', ['customer_order_id'], unique=False)
        op.create_index(op.f('ix_order_assessments_created_at'), 'order_assessments', ['created_at'], unique=False)

    # 2. department_readiness
    if 'department_readiness' not in existing_tables:
        op.create_table(
            'department_readiness',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('assessment_id', sa.Integer(), nullable=False),
            sa.Column('department', sa.String(length=50), nullable=False),
            sa.Column('readiness_status', sa.String(length=50), nullable=False),
            sa.Column('available_evidence', sa.JSON(), nullable=True),
            sa.Column('identified_issue', sa.Text(), nullable=True),
            sa.Column('reason_for_issue', sa.Text(), nullable=True),
            sa.Column('required_action', sa.Text(), nullable=True),
            sa.Column('responsible_role', sa.String(length=100), nullable=True),
            sa.Column('estimated_delay_days', sa.Integer(), nullable=True),
            sa.Column('data_source', sa.String(length=150), nullable=True),
            sa.Column('last_updated_at', sa.DateTime(), nullable=False),
            sa.Column('missing_info', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['assessment_id'], ['order_assessments.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_department_readiness_assessment_id'), 'department_readiness', ['assessment_id'], unique=False)
        op.create_index(op.f('ix_department_readiness_department'), 'department_readiness', ['department'], unique=False)
        op.create_index(op.f('ix_department_readiness_readiness_status'), 'department_readiness', ['readiness_status'], unique=False)
        op.create_index('idx_dept_readiness_assessment', 'department_readiness', ['assessment_id', 'department'], unique=False)

    # 3. order_monitoring_records
    if 'order_monitoring_records' not in existing_tables:
        op.create_table(
            'order_monitoring_records',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('customer_order_id', sa.String(length=50), nullable=False),
            sa.Column('approved_delivery_date', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
            sa.Column('baseline_milestones', sa.JSON(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('last_checked_at', sa.DateTime(), nullable=True),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.Column('closure_reason', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_order_monitoring_records_customer_order_id'), 'order_monitoring_records', ['customer_order_id'], unique=True)
        op.create_index(op.f('ix_order_monitoring_records_approved_delivery_date'), 'order_monitoring_records', ['approved_delivery_date'], unique=False)
        op.create_index(op.f('ix_order_monitoring_records_status'), 'order_monitoring_records', ['status'], unique=False)
        op.create_index(op.f('ix_order_monitoring_records_last_checked_at'), 'order_monitoring_records', ['last_checked_at'], unique=False)

    # 4. monitoring_execution_logs
    if 'monitoring_execution_logs' not in existing_tables:
        op.create_table(
            'monitoring_execution_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('monitoring_record_id', sa.Integer(), nullable=True),
            sa.Column('customer_order_id', sa.String(length=50), nullable=True),
            sa.Column('cycle_type', sa.String(length=50), server_default='SCHEDULED', nullable=False),
            sa.Column('executed_at', sa.DateTime(), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='SUCCESS', nullable=False),
            sa.Column('risks_found_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['monitoring_record_id'], ['order_monitoring_records.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_monitoring_execution_logs_monitoring_record_id'), 'monitoring_execution_logs', ['monitoring_record_id'], unique=False)
        op.create_index(op.f('ix_monitoring_execution_logs_customer_order_id'), 'monitoring_execution_logs', ['customer_order_id'], unique=False)
        op.create_index(op.f('ix_monitoring_execution_logs_executed_at'), 'monitoring_execution_logs', ['executed_at'], unique=False)

    # 5. risk_alerts
    if 'risk_alerts' not in existing_tables:
        op.create_table(
            'risk_alerts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('customer_order_id', sa.String(length=50), nullable=False),
            sa.Column('monitoring_record_id', sa.Integer(), nullable=True),
            sa.Column('department', sa.String(length=50), nullable=False),
            sa.Column('risk_category', sa.String(length=100), nullable=False),
            sa.Column('severity', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('delivery_impact', sa.Text(), nullable=True),
            sa.Column('recommended_action', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='OPEN', nullable=False),
            sa.Column('assigned_owner', sa.String(length=255), nullable=True),
            sa.Column('dedup_fingerprint', sa.String(length=255), nullable=False),
            sa.Column('detected_at', sa.DateTime(), nullable=False),
            sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
            sa.Column('acknowledged_by', sa.Integer(), nullable=True),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('resolved_by', sa.Integer(), nullable=True),
            sa.Column('resolution_notes', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['monitoring_record_id'], ['order_monitoring_records.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id']),
            sa.ForeignKeyConstraint(['resolved_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_risk_alerts_customer_order_id'), 'risk_alerts', ['customer_order_id'], unique=False)
        op.create_index(op.f('ix_risk_alerts_monitoring_record_id'), 'risk_alerts', ['monitoring_record_id'], unique=False)
        op.create_index(op.f('ix_risk_alerts_department'), 'risk_alerts', ['department'], unique=False)
        op.create_index(op.f('ix_risk_alerts_risk_category'), 'risk_alerts', ['risk_category'], unique=False)
        op.create_index(op.f('ix_risk_alerts_severity'), 'risk_alerts', ['severity'], unique=False)
        op.create_index(op.f('ix_risk_alerts_status'), 'risk_alerts', ['status'], unique=False)
        op.create_index(op.f('ix_risk_alerts_dedup_fingerprint'), 'risk_alerts', ['dedup_fingerprint'], unique=False)
        op.create_index(op.f('ix_risk_alerts_detected_at'), 'risk_alerts', ['detected_at'], unique=False)

    # 6. email_notification_logs
    if 'email_notification_logs' not in existing_tables:
        op.create_table(
            'email_notification_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('alert_id', sa.Integer(), nullable=True),
            sa.Column('customer_order_id', sa.String(length=50), nullable=False),
            sa.Column('recipient_email', sa.String(length=255), nullable=False),
            sa.Column('department', sa.String(length=50), nullable=False),
            sa.Column('subject', sa.String(length=255), nullable=False),
            sa.Column('body_text', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='PENDING_CONFIG', nullable=False),
            sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('failure_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('sent_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['alert_id'], ['risk_alerts.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_email_notification_logs_alert_id'), 'email_notification_logs', ['alert_id'], unique=False)
        op.create_index(op.f('ix_email_notification_logs_customer_order_id'), 'email_notification_logs', ['customer_order_id'], unique=False)
        op.create_index(op.f('ix_email_notification_logs_recipient_email'), 'email_notification_logs', ['recipient_email'], unique=False)
        op.create_index(op.f('ix_email_notification_logs_department'), 'email_notification_logs', ['department'], unique=False)
        op.create_index(op.f('ix_email_notification_logs_status'), 'email_notification_logs', ['status'], unique=False)
        op.create_index(op.f('ix_email_notification_logs_created_at'), 'email_notification_logs', ['created_at'], unique=False)

    # 7. department_contacts
    if 'department_contacts' not in existing_tables:
        op.create_table(
            'department_contacts',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('department', sa.String(length=50), nullable=False),
            sa.Column('role_name', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_department_contacts_department'), 'department_contacts', ['department'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    tables = [
        'department_contacts',
        'email_notification_logs',
        'risk_alerts',
        'monitoring_execution_logs',
        'order_monitoring_records',
        'department_readiness',
        'order_assessments',
    ]
    for tbl in tables:
        if tbl in existing_tables:
            op.drop_table(tbl)
