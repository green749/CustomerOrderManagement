from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.auth import User
from ..security.permissions import (
    require_permission,
    require_commercial_approver,
    Permission,
)
from ..services.auth_service import get_current_user
from ..services.workflow_service import WorkflowService
from ..schemas.workflow import (
    CommitmentProposalResponse,
    CommitmentDecisionRequest,
)

router = APIRouter(prefix="/api/commitment-proposals", tags=["Commitment Proposals & Approvals"])


@router.get("", response_model=List[CommitmentProposalResponse])
def get_commitment_proposals(
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status: PENDING, APPROVED, REJECTED"),
    customer_order_id: Optional[str] = Query(default=None, description="Filter by customer order ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """List commercial commitment proposals with optional status filter and customer scoping."""
    return WorkflowService.list_proposals(
        db=db,
        user=current_user,
        status=status_filter,
        customer_order_id=customer_order_id,
    )


@router.get("/{proposal_id}", response_model=CommitmentProposalResponse)
def get_commitment_proposal_by_id(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ORDER_VIEW)),
):
    """Retrieve a single commitment proposal by ID."""
    from ..repositories.commitment_repo import CommitmentRepository
    proposal = CommitmentRepository.get_proposal_by_id(db, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Commitment proposal #{proposal_id} not found."
        )
    return proposal


@router.post("/{proposal_id}/approve", response_model=CommitmentProposalResponse)
def approve_commitment_proposal(
    proposal_id: int,
    body: CommitmentDecisionRequest = CommitmentDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_commercial_approver),
):
    """
    Approve a commercial commitment proposal.
    Restricted to authorized Commercial Approvers with explicit can_approve_commitments authority or Administrator role.
    Customer Service representatives without explicit approval authority are rejected with 403 Forbidden.
    Enforces segregation of duties: Automated agents and creators cannot self-approve.
    """
    try:
        return WorkflowService.approve_proposal(
            db=db,
            proposal_id=proposal_id,
            user=current_user,
            decision_note=body.decision_note,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/{proposal_id}/reject", response_model=CommitmentProposalResponse)
def reject_commitment_proposal(
    proposal_id: int,
    body: CommitmentDecisionRequest = CommitmentDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_commercial_approver),
):
    """
    Reject a commercial commitment proposal.
    Restricted to authorized Commercial Approvers with explicit can_approve_commitments authority or Administrator role.
    """
    try:
        return WorkflowService.reject_proposal(
            db=db,
            proposal_id=proposal_id,
            user=current_user,
            decision_note=body.decision_note,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
