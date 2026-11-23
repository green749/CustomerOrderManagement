from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    department: Optional[str] = None
    can_approve_commitments: bool = False
    is_active: bool
    customer_scope: Optional[list] = None
    created_at: datetime
    permissions: List[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    role: str = Field("operational", description="admin, customer_service, operational")
    department: Optional[str] = Field(None, description="ERP, MMS, MES, WMS, QMS, TMS, PLM")
    can_approve_commitments: bool = False
    customer_scope: Optional[List[str]] = None


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    can_approve_commitments: Optional[bool] = None
    is_active: Optional[bool] = None
    customer_scope: Optional[List[str]] = None
    password: Optional[str] = None


class DepartmentContactRequest(BaseModel):
    department: str = Field(..., description="Department code (ERP, MMS, MES, WMS, QMS, TMS, PLM, CUSTOMER_SERVICE)")
    role_name: str = Field(..., description="Responsible role description")
    email: EmailStr = Field(..., description="Recipient email address")
    is_active: bool = True


class DepartmentMappingRequest(BaseModel):
    issue_category: str
    issue_label: str
    responsible_department: str
    description: Optional[str] = None
    is_active: bool = True


class CustomerCommunicationRequest(BaseModel):
    customer_communication_notes: str = Field(..., min_length=3, description="Details of communication with customer")
    customer_communicated: bool = True
