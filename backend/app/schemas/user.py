from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    is_superadmin: bool
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SchoolMemberRead(BaseModel):
    id: int
    school_id: int
    user_id: int
    role: UserRole
    model_config = ConfigDict(from_attributes=True)


class SchoolMemberCreate(BaseModel):
    user_id: int
    role: UserRole = UserRole.VIEWER


class PersonalAccessTokenCreate(BaseModel):
    name: str
    expires_days: int | None = None  # None = never expires (still revocable)


class PersonalAccessTokenRead(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class PersonalAccessTokenCreated(PersonalAccessTokenRead):
    token: str  # full plaintext token — shown only once, at creation
