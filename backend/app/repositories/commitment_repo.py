from typing import Optional, List
from datetime import date, datetime, timezone
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from ..models.workflow import CommitmentProposal
from ..models.business import FactCustomerOrder


def utcnow():
    return datetime.now(timezone.utc)


class CommitmentRepository:
    @staticmethod
    def get_max_revision(db: Session, customer_order_id: str) -> int:
        rev = (
            db.query(func.max(CommitmentProposal.revision))
            .filter(CommitmentProposal.customer_order_id == customer_order_id)
            .scalar()
        )
        return rev or 0

    @staticmethod
    def create_proposal(
        db: Session,
        customer_order_id: str,
        proposed_date: date,
        recommended_by: str,
        reasons: Optional[List[str]],
        created_by: int,
    ) -> CommitmentProposal:
        max_rev = CommitmentRepository.get_max_revision(db, customer_order_id)
        next_revision = max_rev + 1

        proposal = CommitmentProposal(
            customer_order_id=customer_order_id,
            proposed_date=proposed_date,
            recommended_by=recommended_by,
            reasons=reasons or [],
            status="PENDING",
            created_by=created_by,
            revision=next_revision,
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        return proposal

    @staticmethod
    def get_proposal_by_id(db: Session, proposal_id: int) -> Optional[CommitmentProposal]:
        return db.query(CommitmentProposal).filter(CommitmentProposal.id == proposal_id).first()

    @staticmethod
    def list_proposals(
        db: Session,
        status: Optional[str] = None,
        customer_order_id: Optional[str] = None,
        customer_scope: Optional[List[str]] = None,
    ) -> List[CommitmentProposal]:
        query = db.query(CommitmentProposal)

        if customer_scope:
            query = query.join(
                FactCustomerOrder,
                CommitmentProposal.customer_order_id == FactCustomerOrder.customer_order_id,
            ).filter(FactCustomerOrder.customer_id.in_(customer_scope))

        if status:
            query = query.filter(CommitmentProposal.status == status.upper())
        if customer_order_id:
            clean_id = customer_order_id.replace("PRE-", "")
            query = query.filter(
                (CommitmentProposal.customer_order_id == customer_order_id)
                | (CommitmentProposal.customer_order_id == clean_id)
                | (CommitmentProposal.customer_order_id == f"PRE-{clean_id}")
            )

        return query.order_by(desc(CommitmentProposal.created_at)).all()

    @staticmethod
    def get_latest_approved_proposal(db: Session, customer_order_id: str) -> Optional[CommitmentProposal]:
        return (
            db.query(CommitmentProposal)
            .filter(
                CommitmentProposal.customer_order_id == customer_order_id,
                CommitmentProposal.status == "APPROVED",
            )
            .order_by(desc(CommitmentProposal.revision))
            .first()
        )

    @staticmethod
    def get_latest_proposal(db: Session, customer_order_id: str) -> Optional[CommitmentProposal]:
        return (
            db.query(CommitmentProposal)
            .filter(CommitmentProposal.customer_order_id == customer_order_id)
            .order_by(desc(CommitmentProposal.revision))
            .first()
        )

    @staticmethod
    def approve_proposal(
        db: Session,
        proposal: CommitmentProposal,
        decided_by_user_id: int,
        decision_note: Optional[str] = None,
    ) -> CommitmentProposal:
        if proposal.status != "PENDING":
            raise ValueError(f"Cannot approve proposal {proposal.id}: status is already '{proposal.status}'.")

        # Stale revision check: is there a higher revision for this customer order?
        newer_rev = (
            db.query(CommitmentProposal)
            .filter(
                CommitmentProposal.customer_order_id == proposal.customer_order_id,
                CommitmentProposal.revision > proposal.revision,
            )
            .first()
        )
        if newer_rev:
            raise ValueError(
                f"Cannot approve stale revision {proposal.revision}. "
                f"Newer revision {newer_rev.revision} (ID {newer_rev.id}) already exists."
            )

        proposal.status = "APPROVED"
        proposal.decided_by = decided_by_user_id
        proposal.decided_at = utcnow()
        proposal.decision_note = decision_note
        db.commit()
        db.refresh(proposal)
        return proposal

    @staticmethod
    def reject_proposal(
        db: Session,
        proposal: CommitmentProposal,
        decided_by_user_id: int,
        decision_note: Optional[str] = None,
    ) -> CommitmentProposal:
        if proposal.status != "PENDING":
            raise ValueError(f"Cannot reject proposal {proposal.id}: status is already '{proposal.status}'.")

        newer_rev = (
            db.query(CommitmentProposal)
            .filter(
                CommitmentProposal.customer_order_id == proposal.customer_order_id,
                CommitmentProposal.revision > proposal.revision,
            )
            .first()
        )
        if newer_rev:
            raise ValueError(
                f"Cannot reject stale revision {proposal.revision}. "
                f"Newer revision {newer_rev.revision} (ID {newer_rev.id}) already exists."
            )

        proposal.status = "REJECTED"
        proposal.decided_by = decided_by_user_id
        proposal.decided_at = utcnow()
        proposal.decision_note = decision_note
        db.commit()
        db.refresh(proposal)
        return proposal

