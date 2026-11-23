from typing import Optional, List
from datetime import date
from sqlalchemy.orm import Session
from ..repositories.commitment_repo import CommitmentRepository
from ..repositories.audit_repo import AuditRepository
from ..repositories.order_repo import OrderRepository
from ..models.workflow import CommitmentProposal
from ..models.auth import User
from .promise_service import recommend_promise_date
from .cache_service import invalidate_cache


class WorkflowService:
    @staticmethod
    def create_commitment_proposal(
        db: Session,
        customer_order_id: str,
        user: User,
        proposed_date: Optional[date] = None,
        recommended_by: str = "agent",
        reasons: Optional[List[str]] = None,
    ) -> CommitmentProposal:
        # Check order existence and customer scope
        order = OrderRepository.get_order_by_id(db, customer_order_id, customer_scope=user.customer_scope)
        if not order:
            raise ValueError(f"Customer order '{customer_order_id}' was not found or not accessible within user scope.")

        # If proposed_date is not provided, generate from promise recommendation engine
        final_reasons = list(reasons or [])
        if not proposed_date:
            rec = recommend_promise_date(db, customer_order_id)
            proposed_date = rec.recommended_date
            if not final_reasons:
                final_reasons = rec.explanations or [f"Promise recommendation engine calculated feasible date based on ATP/CTP."]

        proposal = CommitmentRepository.create_proposal(
            db=db,
            customer_order_id=customer_order_id,
            proposed_date=proposed_date,
            recommended_by=recommended_by,
            reasons=final_reasons,
            created_by=user.id,
        )

        # Audit log
        AuditRepository.log(
            db=db,
            action="CREATE_PROPOSAL",
            entity="commitment_proposal",
            entity_id=str(proposal.id),
            user_id=user.id,
            payload={
                "customer_order_id": customer_order_id,
                "proposed_date": str(proposed_date),
                "revision": proposal.revision,
                "recommended_by": recommended_by,
                "reasons": final_reasons,
            },
        )

        # All proposals strictly require human approval; auto-approval has been permanently removed.
        proposal.status = "PENDING"
        db.commit()

        invalidate_cache()
        return proposal

    @staticmethod
    def list_proposals(
        db: Session,
        user: User,
        status: Optional[str] = None,
        customer_order_id: Optional[str] = None,
    ) -> List[CommitmentProposal]:
        return CommitmentRepository.list_proposals(
            db=db,
            status=status,
            customer_order_id=customer_order_id,
            customer_scope=user.customer_scope,
        )

    @staticmethod
    def approve_proposal(
        db: Session,
        proposal_id: int,
        user: User,
        decision_note: Optional[str] = None,
    ) -> CommitmentProposal:
        proposal = CommitmentRepository.get_proposal_by_id(db, proposal_id)
        if not proposal:
            raise ValueError(f"Commitment proposal with ID {proposal_id} was not found.")

        # Segregation of duties: Creator cannot approve their own proposal unless administrator
        if proposal.created_by == user.id and user.role != "admin":
            raise ValueError(
                "Segregation of duties violation: Users cannot approve their own commitment proposals. "
                "Another authorized manager or administrator must review and approve."
            )

        # Check scope on the underlying order (allow PRE- pre-confirmation assessments)
        if not proposal.customer_order_id.startswith("PRE-"):
            order = OrderRepository.get_order_by_id(db, proposal.customer_order_id, customer_scope=user.customer_scope)
            if not order:
                raise ValueError(f"Order '{proposal.customer_order_id}' is not accessible within user scope.")

        approved_prop = CommitmentRepository.approve_proposal(
            db=db,
            proposal=proposal,
            decided_by_user_id=user.id,
            decision_note=decision_note,
        )

        # Synchronize order lifecycle state in FactCustomerOrder
        try:
            ord_rec = OrderRepository.get_order_by_id(db, approved_prop.customer_order_id)
            if ord_rec:
                ord_rec.order_status = "IN_PRODUCTION"
                ord_rec.confirmed_delivery_date = approved_prop.proposed_date
                db.commit()
        except Exception:
            pass

        # Trigger Agent 3: Activate monitoring for approved commitment
        try:
            from .monitoring_service import MonitoringService, notify_order_changed
            MonitoringService.activate_monitoring(
                db=db,
                customer_order_id=approved_prop.customer_order_id,
                approved_delivery_date=approved_prop.proposed_date,
                user_id=user.id,
            )
            notify_order_changed(approved_prop.customer_order_id, db=db)
        except Exception as mon_err:
            logger.exception(f"Failed to activate monitoring for approved proposal #{approved_prop.id}: {mon_err}")
            AuditRepository.log(
                db=db,
                action="MONITORING_ACTIVATION_FAILED",
                entity="order_monitoring_record",
                entity_id=approved_prop.customer_order_id,
                user_id=user.id,
                payload={"error": str(mon_err), "proposal_id": approved_prop.id},
            )

        # Audit log
        AuditRepository.log(
            db=db,
            action="APPROVE_PROPOSAL",
            entity="commitment_proposal",
            entity_id=str(approved_prop.id),
            user_id=user.id,
            payload={
                "customer_order_id": approved_prop.customer_order_id,
                "proposed_date": str(approved_prop.proposed_date),
                "revision": approved_prop.revision,
                "decision_note": decision_note,
            },
        )
        # Dispatch official Customer Order Commitment & Delivery Confirmation Email
        try:
            from .email_service import EmailService
            EmailService.send_customer_order_approval_notification(
                db=db,
                proposal=approved_prop,
                decision_note=decision_note,
                approved_by_user=user,
            )
        except Exception as email_err:
            logger.exception(f"Failed to dispatch customer order confirmation email: {email_err}")

        invalidate_cache()
        return approved_prop

    @staticmethod
    def reject_proposal(
        db: Session,
        proposal_id: int,
        user: User,
        decision_note: Optional[str] = None,
    ) -> CommitmentProposal:
        proposal = CommitmentRepository.get_proposal_by_id(db, proposal_id)
        if not proposal:
            raise ValueError(f"Commitment proposal with ID {proposal_id} was not found.")

        # Check scope on the underlying order
        if not proposal.customer_order_id.startswith("PRE-"):
            order = OrderRepository.get_order_by_id(db, proposal.customer_order_id, customer_scope=user.customer_scope)
            if not order:
                raise ValueError(f"Order '{proposal.customer_order_id}' is not accessible within user scope.")

        rejected_prop = CommitmentRepository.reject_proposal(
            db=db,
            proposal=proposal,
            decided_by_user_id=user.id,
            decision_note=decision_note,
        )

        # Synchronize order lifecycle state in FactCustomerOrder
        try:
            ord_rec = OrderRepository.get_order_by_id(db, rejected_prop.customer_order_id)
            if ord_rec:
                ord_rec.order_status = "CANCELLED"
                db.commit()
            # Ensure monitoring record is cleaned up if proposal was rejected
            from ..models.workflow import OrderMonitoringRecord, RiskAlert
            m_rec = db.query(OrderMonitoringRecord).filter(OrderMonitoringRecord.customer_order_id == rejected_prop.customer_order_id).first()
            if m_rec:
                db.query(RiskAlert).filter(RiskAlert.monitoring_record_id == m_rec.id).delete()
                db.delete(m_rec)
                db.commit()
        except Exception:
            pass

        # Audit log
        AuditRepository.log(
            db=db,
            action="REJECT_PROPOSAL",
            entity="commitment_proposal",
            entity_id=str(rejected_prop.id),
            user_id=user.id,
            payload={
                "customer_order_id": rejected_prop.customer_order_id,
                "proposed_date": str(rejected_prop.proposed_date),
                "revision": rejected_prop.revision,
                "decision_note": decision_note,
            },
        )
        invalidate_cache()
        return rejected_prop

