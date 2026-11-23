from enum import Enum
from typing import List, Set, Optional, Callable
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.auth import User
from ..services.auth_service import get_current_user


class Permission(str, Enum):
    # User Management & Administration
    USER_MANAGE = "user:manage"
    SYSTEM_CONFIG = "system:config"
    AUDIT_VIEW = "audit:view"

    # Department & Notification Configuration
    NOTIFICATION_CONFIG = "notification:config"
    NOTIFICATION_RETRY = "notification:retry"
    NOTIFICATION_VIEW = "notification:view"

    # Orders
    ORDER_VIEW = "order:view"
    ORDER_CREATE = "order:create"
    ORDER_DELIVER = "order:deliver"

    # Agent 2: Feasibility Assessments
    ASSESSMENT_VIEW = "assessment:view"
    ASSESSMENT_CREATE = "assessment:create"

    # Commercial Commitment Approval
    COMMITMENT_APPROVE = "commitment:approve"

    # Agent 3: Monitoring & Surveillance
    MONITORING_VIEW = "monitoring:view"
    MONITORING_TRIGGER = "monitoring:trigger"

    # Risk Alerts & Operational Actions
    ALERT_VIEW = "alert:view"
    ALERT_ACKNOWLEDGE = "alert:acknowledge"
    ALERT_RESOLVE = "alert:resolve"

    # Customer Service Communication
    COMMUNICATION_RECORD = "communication:record"


# Base role-to-permissions mapping
ROLE_PERMISSIONS = {
    "admin": {
        Permission.USER_MANAGE,
        Permission.SYSTEM_CONFIG,
        Permission.AUDIT_VIEW,
        Permission.NOTIFICATION_CONFIG,
        Permission.NOTIFICATION_RETRY,
        Permission.NOTIFICATION_VIEW,
        Permission.ORDER_VIEW,
        Permission.ORDER_CREATE,
        Permission.ORDER_DELIVER,
        Permission.ASSESSMENT_VIEW,
        Permission.ASSESSMENT_CREATE,
        Permission.COMMITMENT_APPROVE,
        Permission.MONITORING_VIEW,
        Permission.MONITORING_TRIGGER,
        Permission.ALERT_VIEW,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.ALERT_RESOLVE,
        Permission.COMMUNICATION_RECORD,
    },
    "customer_service": {
        Permission.ORDER_VIEW,
        Permission.ORDER_CREATE,
        Permission.ASSESSMENT_VIEW,
        Permission.ASSESSMENT_CREATE,
        Permission.MONITORING_VIEW,
        Permission.ALERT_VIEW,
        Permission.COMMUNICATION_RECORD,
        Permission.NOTIFICATION_VIEW,
    },
    "operational": {
        Permission.ORDER_VIEW,
        Permission.ASSESSMENT_VIEW,
        Permission.MONITORING_VIEW,
        Permission.ALERT_VIEW,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.ALERT_RESOLVE,
        Permission.NOTIFICATION_VIEW,
    },
    # Backwards compatibility for manager / operator
    "manager": {
        Permission.ORDER_VIEW,
        Permission.ORDER_CREATE,
        Permission.ASSESSMENT_VIEW,
        Permission.ASSESSMENT_CREATE,
        Permission.COMMITMENT_APPROVE,
        Permission.MONITORING_VIEW,
        Permission.MONITORING_TRIGGER,
        Permission.ALERT_VIEW,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.ALERT_RESOLVE,
        Permission.COMMUNICATION_RECORD,
        Permission.NOTIFICATION_VIEW,
        Permission.NOTIFICATION_RETRY,
    },
    "operator": {
        Permission.ORDER_VIEW,
        Permission.ORDER_CREATE,
        Permission.ASSESSMENT_VIEW,
        Permission.MONITORING_VIEW,
        Permission.ALERT_VIEW,
        Permission.ALERT_ACKNOWLEDGE,
        Permission.NOTIFICATION_VIEW,
    },
    "system": {
        Permission.ORDER_VIEW,
        Permission.ORDER_CREATE,
        Permission.ASSESSMENT_VIEW,
        Permission.ASSESSMENT_CREATE,
        Permission.COMMITMENT_APPROVE,
        Permission.MONITORING_VIEW,
        Permission.MONITORING_TRIGGER,
        Permission.ALERT_VIEW,
    },
}


def get_user_permissions(user: User) -> Set[Permission]:
    """
    Computes effective set of permissions for a user based on:
    1. Assigned role
    2. Explicit approval authority (can_approve_commitments)
    """
    if not user or not user.is_active:
        return set()

    role_key = (user.role or "operational").lower().strip()
    perms = set(ROLE_PERMISSIONS.get(role_key, set()))

    # If user has explicit approval permission, grant COMMITMENT_APPROVE
    if getattr(user, "can_approve_commitments", False):
        perms.add(Permission.COMMITMENT_APPROVE)

    return perms


def has_permission(user: User, permission: Permission) -> bool:
    """Check if user has a specific permission."""
    return permission in get_user_permissions(user)


def require_permission(permission: Permission) -> Callable:
    """
    FastAPI dependency factory enforcing that the authenticated user possesses
    the requested permission. Returns 403 Forbidden if permission is missing,
    or 401 if unauthenticated.
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_perms = get_user_permissions(current_user)
        if permission not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Required permission '{permission.value}' not granted.",
            )
        return current_user

    return permission_checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency requiring Administrator role."""
    role_key = (current_user.role or "").lower().strip()
    if role_key != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Requires Administrator role.",
        )
    return current_user


def require_commercial_approver(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency requiring commercial commitment approval authority.
    Only users with can_approve_commitments=True or Administrator role are permitted.
    """
    if not has_permission(current_user, Permission.COMMITMENT_APPROVE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Commercial commitment approval authority required.",
        )
    return current_user


def verify_department_access(user: User, department: str) -> None:
    """
    Enforces department-level data access boundaries.
    Operational users may only view or mutate records belonging to their assigned department.
    Administrators and Customer Service users are granted cross-department operational visibility.
    """
    role_key = (user.role or "").lower().strip()
    if role_key in ["admin", "manager", "customer_service"]:
        return  # Cross-department permitted

    user_dept = (user.department or "").upper().strip()
    target_dept = (department or "").upper().strip()

    if not user_dept or user_dept != target_dept:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Operational user assigned to '{user_dept or 'None'}' cannot access restricted department '{target_dept}'.",
        )
