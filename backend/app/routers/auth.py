import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, PersonalAccessToken
from app.schemas.user import (
    UserCreate, UserRead, Token,
    PersonalAccessTokenCreate, PersonalAccessTokenRead, PersonalAccessTokenCreated,
)
from app.config import settings

TOKEN_PREFIX = "skb_"

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if user is None:
        raise credentials_exc
    return user


@router.post("/register", response_model=UserRead, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username, User.is_active == True).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return Token(access_token=create_access_token(user.email))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# --- Personal access tokens (long-lived, revocable; for MCP clients) ---

@router.post("/personal-tokens", response_model=PersonalAccessTokenCreated, status_code=201)
def create_personal_token(
    body: PersonalAccessTokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint a long-lived API token for this user. The plaintext is returned ONCE here and
    never stored — only its SHA-256 hash is kept. Use it as a Bearer token against the MCP server."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    expires_at = None
    if body.expires_days and body.expires_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)
    pat = PersonalAccessToken(
        user_id=current_user.id,
        name=body.name,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        prefix=raw[: len(TOKEN_PREFIX) + 6],
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db.add(pat)
    db.commit()
    db.refresh(pat)
    return PersonalAccessTokenCreated(
        id=pat.id, name=pat.name, prefix=pat.prefix, created_at=pat.created_at,
        last_used_at=pat.last_used_at, expires_at=pat.expires_at, token=raw,
    )


@router.get("/personal-tokens", response_model=list[PersonalAccessTokenRead])
def list_personal_tokens(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(PersonalAccessToken)
        .filter(PersonalAccessToken.user_id == current_user.id)
        .order_by(PersonalAccessToken.created_at.desc())
        .all()
    )


@router.delete("/personal-tokens/{token_id}", status_code=204)
def revoke_personal_token(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke (delete) a token. It stops working immediately."""
    pat = db.query(PersonalAccessToken).filter(
        PersonalAccessToken.id == token_id, PersonalAccessToken.user_id == current_user.id
    ).first()
    if not pat:
        raise HTTPException(404, "Token not found")
    db.delete(pat)
    db.commit()
