from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings
from ..schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
    UserCreateRequest,
    UserUpdateRequest,
    DepartmentContactRequest,
    DepartmentMappingRequest,
)
from ..schemas.common import StandardResponse
from ..models.auth import User
from ..models.workflow import DepartmentContact, DepartmentMapping, SystemSetting
from ..repositories.audit_repo import AuditRepository
from ..security.permissions import require_admin, Permission, get_user_permissions
from ..services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    get_current_user,
    hash_password,
    build_user_response,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication & Access Control"])

REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate user with email and password, return JWT tokens with RBAC claims."""
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user)
    raw_refresh, _ = create_refresh_token(db, user.id)
    db.commit()

    # Set secure HttpOnly cookie for refresh token
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="Bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=build_user_response(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: Session = Depends(get_db),
):
    """Rotate refresh token and issue new access & refresh tokens."""
    raw_token = None
    if body and body.refresh_token:
        raw_token = body.refresh_token
    else:
        raw_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from request body and cookie",
        )

    token_resp, new_raw_refresh = rotate_refresh_token(db, raw_token)

    # Set rotated cookie
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_raw_refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )

    return token_resp


@router.post("/logout", response_model=StandardResponse[dict])
def logout(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke refresh token and clear auth cookies."""
    raw_token = None
    if body and body.refresh_token:
        raw_token = body.refresh_token
    else:
        raw_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if raw_token:
        revoke_refresh_token(db, raw_token)

    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth")

    return StandardResponse(
        success=True,
        message="Logged out successfully",
        data={"user_id": current_user.id},
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile and active permissions."""
    return build_user_response(current_user)


# ==============================================================================
# RBAC: USER MANAGEMENT (ADMINISTRATOR ONLY)
# ==============================================================================

@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """List all registered users. Restricted to Administrator role."""
    users = db.query(User).order_by(User.id.asc()).all()
    return [build_user_response(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Create a new application user and assign role/department. Restricted to Administrator."""
    email_clean = payload.email.lower().strip()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User with email '{email_clean}' already exists.")

    new_user = User(
        email=email_clean,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=payload.role.lower().strip(),
        department=payload.department.upper().strip() if payload.department else None,
        can_approve_commitments=payload.can_approve_commitments,
        customer_scope=payload.customer_scope,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Audit logging
    AuditRepository.log(
        db=db,
        action="CREATE_USER",
        entity="user",
        entity_id=str(new_user.id),
        user_id=admin_user.id,
        payload={
            "created_email": new_user.email,
            "role": new_user.role,
            "department": new_user.department,
            "can_approve_commitments": new_user.can_approve_commitments,
        },
    )

    return build_user_response(new_user)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Update user identity, role, department, or approval permission. Restricted to Administrator."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User ID {user_id} not found.")

    changes = {}
    if payload.full_name is not None:
        target_user.full_name = payload.full_name.strip()
        changes["full_name"] = target_user.full_name
    if payload.role is not None:
        target_user.role = payload.role.lower().strip()
        changes["role"] = target_user.role
    if payload.department is not None:
        target_user.department = payload.department.upper().strip() if payload.department else None
        changes["department"] = target_user.department
    if payload.can_approve_commitments is not None:
        target_user.can_approve_commitments = payload.can_approve_commitments
        changes["can_approve_commitments"] = target_user.can_approve_commitments
    if payload.is_active is not None:
        target_user.is_active = payload.is_active
        changes["is_active"] = target_user.is_active
    if payload.customer_scope is not None:
        target_user.customer_scope = payload.customer_scope
        changes["customer_scope"] = target_user.customer_scope
    if payload.password:
        target_user.hashed_password = hash_password(payload.password)
        changes["password_reset"] = True

    db.commit()
    db.refresh(target_user)

    # Audit logging
    AuditRepository.log(
        db=db,
        action="UPDATE_USER_PERMISSIONS",
        entity="user",
        entity_id=str(target_user.id),
        user_id=admin_user.id,
        payload=changes,
    )

    return build_user_response(target_user)


@router.delete("/users/{user_id}", response_model=StandardResponse[dict])
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Deactivate user access. Restricted to Administrator."""
    if user_id == admin_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administrators cannot deactivate their own account.")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User ID {user_id} not found.")

    target_user.is_active = False
    db.commit()

    AuditRepository.log(
        db=db,
        action="DEACTIVATE_USER",
        entity="user",
        entity_id=str(target_user.id),
        user_id=admin_user.id,
        payload={"email": target_user.email},
    )

    return StandardResponse(success=True, message=f"User '{target_user.email}' deactivated successfully.", data={"user_id": user_id})


# ==============================================================================
# DEPARTMENT RESPONSIBILITY MAPPINGS & CONTACT CONFIGURATION (ADMINISTRATOR)
# ==============================================================================

DEFAULT_MAPPINGS = [
    {
        "issue_category": "PO_COMMERCIAL_VALIDATION",
        "issue_label": "PO, commercial or order validation",
        "responsible_department": "ERP",
        "description": "Commercial pricing, customer credit check, and sales order header alignment in SAP/ERP.",
    },
    {
        "issue_category": "RAW_MATERIAL_SHORTAGE",
        "issue_label": "Raw material shortage",
        "responsible_department": "MMS",
        "description": "Bill of Materials raw inventory levels, supplier lead-time shortages, and replenishment.",
    },
    {
        "issue_category": "PRODUCTION_DELAY_CAPACITY",
        "issue_label": "Production delays or capacity issues",
        "responsible_department": "MES",
        "description": "Assembly line bottleneck, station downtime, capacity constraints, and work order schedule.",
    },
    {
        "issue_category": "WAREHOUSE_PICKING_PACKAGING",
        "issue_label": "Warehouse, picking or packaging issues",
        "responsible_department": "WMS",
        "description": "Finished goods staging, picking exceptions, palletization, and export packaging.",
    },
    {
        "issue_category": "INSPECTION_QUALITY_HOLD",
        "issue_label": "Inspection, quality hold or release issues",
        "responsible_department": "QMS",
        "description": "First-pass inspection failures, station rework flags, disposition holds, and batch scrap.",
    },
    {
        "issue_category": "CARRIER_DISPATCH_TRANSIT",
        "issue_label": "Carrier, dispatch or transit issues",
        "responsible_department": "TMS",
        "description": "Carrier vehicle allocation, EDI 214 transit milestone exceptions, hub delay, and tracking.",
    },
    {
        "issue_category": "PRODUCT_CONFIG_ENGINEERING_REVISION",
        "issue_label": "Product configuration or engineering revision",
        "responsible_department": "PLM",
        "description": "Engineering change orders (ECO), firmware revision alignment, and BOM variant validation.",
    },
]


@router.get("/department-mappings")
def list_department_mappings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List configurable mappings between issue categories and responsible departments."""
    existing = db.query(DepartmentMapping).order_by(DepartmentMapping.responsible_department.asc()).all()
    if not existing:
        # Seed defaults
        for m in DEFAULT_MAPPINGS:
            db_map = DepartmentMapping(
                issue_category=m["issue_category"],
                issue_label=m["issue_label"],
                responsible_department=m["responsible_department"],
                description=m["description"],
                is_active=True,
            )
            db.add(db_map)
        db.commit()
        existing = db.query(DepartmentMapping).order_by(DepartmentMapping.responsible_department.asc()).all()

    return [
        {
            "id": item.id,
            "issue_category": item.issue_category,
            "issue_label": item.issue_label,
            "responsible_department": item.responsible_department,
            "description": item.description,
            "is_active": item.is_active,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        for item in existing
    ]


@router.put("/department-mappings/{mapping_id}")
def update_department_mapping(
    mapping_id: int,
    payload: DepartmentMappingRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Configure responsible department mapping. Restricted to Administrator."""
    mapping = db.query(DepartmentMapping).filter(DepartmentMapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mapping ID {mapping_id} not found.")

    mapping.responsible_department = payload.responsible_department.upper().strip()
    mapping.issue_label = payload.issue_label.strip()
    mapping.description = payload.description
    mapping.is_active = payload.is_active
    db.commit()

    AuditRepository.log(
        db=db,
        action="UPDATE_DEPARTMENT_MAPPING",
        entity="department_mapping",
        entity_id=str(mapping.id),
        user_id=admin_user.id,
        payload={
            "issue_category": mapping.issue_category,
            "responsible_department": mapping.responsible_department,
            "is_active": mapping.is_active,
        },
    )

    return {"message": "Department mapping updated successfully", "mapping_id": mapping.id}


@router.get("/department-contacts")
def list_all_contacts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all department and customer service alert notification recipients."""
    contacts = db.query(DepartmentContact).order_by(DepartmentContact.department.asc()).all()
    return [
        {
            "id": c.id,
            "department": c.department,
            "role_name": c.role_name,
            "email": c.email,
            "is_active": c.is_active,
        }
        for c in contacts
    ]


@router.post("/department-contacts")
def create_or_update_contact(
    payload: DepartmentContactRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Configure notification recipients for operational departments or Customer Service. Restricted to Administrator."""
    dept_code = payload.department.upper().strip()
    existing = db.query(DepartmentContact).filter(DepartmentContact.department == dept_code).first()
    if existing:
        existing.role_name = payload.role_name.strip()
        existing.email = str(payload.email).strip().lower()
        existing.is_active = payload.is_active
        contact = existing
    else:
        contact = DepartmentContact(
            department=dept_code,
            role_name=payload.role_name.strip(),
            email=str(payload.email).strip().lower(),
            is_active=payload.is_active,
        )
        db.add(contact)

    db.commit()
    db.refresh(contact)

    AuditRepository.log(
        db=db,
        action="UPDATE_NOTIFICATION_RECIPIENT",
        entity="department_contact",
        entity_id=str(contact.id),
        user_id=admin_user.id,
        payload={
            "department": contact.department,
            "email": contact.email,
            "role_name": contact.role_name,
            "is_active": contact.is_active,
        },
    )

    return {
        "id": contact.id,
        "department": contact.department,
        "role_name": contact.role_name,
        "email": contact.email,
        "is_active": contact.is_active,
    }


class SmtpConfigRequest(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None


@router.get("/smtp-config")
def get_smtp_config(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Retrieve SMTP relay configuration (password masked)."""
    import os
    from ..config import settings

    settings_dict = {s.key: s.value for s in db.query(SystemSetting).all()}
    host = settings_dict.get("smtp_host") or os.environ.get("SMTP_HOST") or getattr(settings, "smtp_host", None)
    user = settings_dict.get("smtp_user") or os.environ.get("SMTP_USER") or getattr(settings, "smtp_user", None)
    port = settings_dict.get("smtp_port") or os.environ.get("SMTP_PORT") or getattr(settings, "smtp_port", 587)
    sender = settings_dict.get("smtp_from") or os.environ.get("SMTP_FROM") or getattr(settings, "smtp_from", "noreply@manufacturing.internal")
    has_pass = bool(settings_dict.get("smtp_password") or os.environ.get("SMTP_PASSWORD") or getattr(settings, "smtp_password", None))

    return {
        "smtp_host": host,
        "smtp_port": int(port) if port else 587,
        "smtp_user": user,
        "has_password": has_pass,
        "smtp_from": sender,
        "is_configured": bool(host and user and has_pass),
    }


@router.post("/smtp-config")
def update_smtp_config(
    payload: SmtpConfigRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Configure enterprise SMTP relay credentials. Restricted to Administrator."""
    def set_setting(key: str, val: Optional[str]):
        if val is not None:
            s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if not s:
                s = SystemSetting(key=key, value=val)
                db.add(s)
            else:
                s.value = val

    if payload.smtp_host is not None:
        set_setting("smtp_host", payload.smtp_host.strip())
    if payload.smtp_port is not None:
        set_setting("smtp_port", str(payload.smtp_port))
    if payload.smtp_user is not None:
        set_setting("smtp_user", payload.smtp_user.strip())
    if payload.smtp_password is not None and payload.smtp_password != "":
        set_setting("smtp_password", payload.smtp_password)
    if payload.smtp_from is not None:
        set_setting("smtp_from", payload.smtp_from.strip())

    db.commit()

    AuditRepository.log(
        db=db,
        action="UPDATE_SMTP_CONFIG",
        entity="system_settings",
        entity_id="smtp",
        user_id=admin_user.id,
        payload={"smtp_host": payload.smtp_host, "smtp_user": payload.smtp_user},
    )

    return {"message": "SMTP configuration updated successfully."}

