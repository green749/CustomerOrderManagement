import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.auth import User, RefreshToken
from ..schemas.auth import TokenResponse, UserResponse

ph = PasswordHasher()
security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash password securely using Argon2."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2 hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def hash_token(raw_token: str) -> str:
    """Hash opaque token using SHA-256 for secure database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(user: User) -> str:
    """Create short-lived JWT access token (15 mins)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "department": getattr(user, "department", None),
        "can_approve_commitments": getattr(user, "can_approve_commitments", False),
        "name": user.full_name,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def build_user_response(user: User) -> UserResponse:
    from ..security.permissions import get_user_permissions
    resp = UserResponse.model_validate(user)
    resp.permissions = [p.value for p in get_user_permissions(user)]
    return resp


def create_refresh_token(db: Session, user_id: int) -> Tuple[str, RefreshToken]:
    """Create opaque refresh token and store hash in DB."""
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)

    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(db_token)
    db.flush()
    return raw_token, db_token


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password."""
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def rotate_refresh_token(db: Session, raw_refresh_token: str) -> Tuple[TokenResponse, str]:
    """Rotate an opaque refresh token and issue a new token pair."""
    token_hash = hash_token(raw_refresh_token)
    now = datetime.utcnow()

    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if db_token.is_revoked:
        # Potential token reuse attack: revoke all tokens for this user
        db.query(RefreshToken).filter(RefreshToken.user_id == db_token.user_id).update(
            {"is_revoked": True}
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Revoked refresh token reuse detected. All sessions terminated.",
        )

    if db_token.expires_at < now:
        db_token.is_revoked = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired refresh token",
        )

    user = db.query(User).filter(User.id == db_token.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer active",
        )

    # Revoke current token and generate replacement
    db_token.is_revoked = True

    new_raw_refresh, new_db_token = create_refresh_token(db, user.id)
    db_token.replaced_by_hash = new_db_token.token_hash
    db.commit()

    access_token = create_access_token(user)

    token_resp = TokenResponse(
        access_token=access_token,
        refresh_token=new_raw_refresh,
        token_type="Bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=build_user_response(user),
    )
    return token_resp, new_raw_refresh


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> bool:
    """Revoke a refresh token on logout."""
    token_hash = hash_token(raw_refresh_token)
    db_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )
    if db_token:
        db_token.is_revoked = True
        db.commit()
        return True
    return False


def require_role(allowed_roles: List[str]):
    """Role-based access dependency."""
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires role in {allowed_roles}",
            )
        return user
    return role_checker


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Validate Bearer JWT access token and return the authenticated user."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        user_id = int(user_id_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def ensure_seed_users(db: Session) -> None:
    """Ensure baseline admin and demo seed users exist and credentials match settings."""
    try:
        if settings.admin_email and settings.admin_password:
            admin = db.query(User).filter(User.email == settings.admin_email.lower().strip()).first()
            if not admin:
                admin = User(
                    email=settings.admin_email.lower().strip(),
                    hashed_password=hash_password(settings.admin_password),
                    full_name=settings.admin_full_name,
                    role="admin",
                    is_active=True,
                )
                db.add(admin)
            elif not verify_password(settings.admin_password, admin.hashed_password):
                admin.hashed_password = hash_password(settings.admin_password)
                admin.is_active = True

        if settings.demo_email and settings.demo_password:
            demo = db.query(User).filter(User.email == settings.demo_email.lower().strip()).first()
            if not demo:
                demo = User(
                    email=settings.demo_email.lower().strip(),
                    hashed_password=hash_password(settings.demo_password),
                    full_name=settings.demo_full_name,
                    role="manager",
                    is_active=True,
                )
                db.add(demo)
            elif not verify_password(settings.demo_password, demo.hashed_password):
                demo.hashed_password = hash_password(settings.demo_password)
                demo.is_active = True

        db.commit()
    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger("manufacturing.auth").warning(f"Seed users synchronization note: {e}")

