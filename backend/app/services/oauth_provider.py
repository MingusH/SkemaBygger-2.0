"""Self-hosted OAuth 2.1 Authorization Server backing MCP client logins.

The OAuth flow authenticates against the existing User table via a login page
(app/routers/oauth_login.py). This provider implements the FastMCP/MCP-SDK provider
contract and persists protocol state in the oauth_* tables.

Token strategy:
  - access tokens  : stateless JWTs (sub = user email, typ = "mcp_access"), short-lived,
                     verified by decoding — no DB hit per request.
  - refresh tokens : random opaque strings; only the SHA-256 hash is stored, rotated on use.
  - auth codes     : random opaque strings, one-time (deleted on exchange), PKCE-bound.

The MCP tools resolve identity from the access token's `sub` claim (see mcp_server.py).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from mcp.server.auth.provider import (
    AccessToken, AuthorizationCode, AuthorizationParams, AuthorizeError,
    RefreshToken, TokenError, construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from fastmcp.server.auth.auth import OAuthProvider, ClientRegistrationOptions, RevocationOptions

from app.config import settings
from app.database import SessionLocal
from app.models.oauth import OAuthClient, OAuthAuthCode, OAuthRefreshToken

ACCESS_TTL_SECONDS = 60 * 60            # 1 hour
AUTH_CODE_TTL_SECONDS = 5 * 60          # 5 minutes
REFRESH_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_access_token(email: str, client_id: str, scopes: list[str]) -> str:
    """Mint a stateless access-token JWT for a logged-in user."""
    now = _now()
    payload = {
        "sub": email,
        "client_id": client_id,
        "scope": " ".join(scopes),
        "typ": "mcp_access",
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_auth_code(*, client_id: str, user_email: str, redirect_uri: str,
                     redirect_uri_provided_explicitly: bool, scopes: list[str],
                     code_challenge: str | None) -> str:
    """Persist a fresh authorization code (called by the login page on success)."""
    code = "skbc_" + secrets.token_urlsafe(32)
    with SessionLocal() as db:
        db.add(OAuthAuthCode(
            code=code,
            client_id=client_id,
            user_email=user_email,
            redirect_uri=redirect_uri,
            redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
            scopes=" ".join(scopes),
            code_challenge=code_challenge,
            expires_at=_now() + timedelta(seconds=AUTH_CODE_TTL_SECONDS),
        ))
        db.commit()
    return code


class DBOAuthProvider(OAuthProvider):
    def __init__(self, base_url: str):
        super().__init__(
            base_url=base_url,
            client_registration_options=ClientRegistrationOptions(enabled=True),
            revocation_options=RevocationOptions(enabled=True),
        )

    # ── Dynamic client registration ──────────────────────────────────────────
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with SessionLocal() as db:
            row = db.get(OAuthClient, client_id)
            return OAuthClientInformationFull.model_validate_json(row.client_data) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        with SessionLocal() as db:
            row = db.get(OAuthClient, client_info.client_id)
            data = client_info.model_dump_json()
            if row:
                row.client_data = data
                row.client_secret = client_info.client_secret
            else:
                db.add(OAuthClient(
                    client_id=client_info.client_id,
                    client_secret=client_info.client_secret,
                    client_data=data,
                    created_at=_now(),
                ))
            db.commit()

    # ── Authorization: hand off to our own login page ────────────────────────
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        """Don't auto-approve. Redirect the browser to our login page, carrying the
        request in a short-lived signed JWT; the login page issues the code on success."""
        req = jwt.encode(
            {
                "client_id": client.client_id,
                "redirect_uri": str(params.redirect_uri),
                "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                "scopes": params.scopes or [],
                "state": params.state,
                "code_challenge": params.code_challenge,
                "typ": "mcp_authreq",
                "exp": _now() + timedelta(minutes=10),
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        return f"{settings.public_base_url}/oauth/login?req={req}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        with SessionLocal() as db:
            row = db.get(OAuthAuthCode, authorization_code)
            if not row or row.client_id != client.client_id:
                return None
            if row.expires_at < _now():
                db.delete(row)
                db.commit()
                return None
            return AuthorizationCode(
                code=row.code,
                client_id=row.client_id,
                redirect_uri=row.redirect_uri,
                redirect_uri_provided_explicitly=row.redirect_uri_provided_explicitly,
                scopes=row.scopes.split() if row.scopes else [],
                expires_at=row.expires_at.timestamp(),
                code_challenge=row.code_challenge,
            )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        with SessionLocal() as db:
            row = db.get(OAuthAuthCode, authorization_code.code)
            if not row:
                raise TokenError("invalid_grant", "Authorization code not found or already used.")
            user_email = row.user_email
            scopes = row.scopes.split() if row.scopes else []
            db.delete(row)  # one-time use
            db.commit()
        return self._issue_tokens(client.client_id, user_email, scopes)

    # ── Refresh tokens (rotated) ─────────────────────────────────────────────
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        with SessionLocal() as db:
            row = db.get(OAuthRefreshToken, _hash(refresh_token))
            if not row or row.client_id != client.client_id:
                return None
            if row.expires_at is not None and row.expires_at < _now():
                db.delete(row)
                db.commit()
                return None
            return RefreshToken(
                token=refresh_token,
                client_id=row.client_id,
                scopes=row.scopes.split() if row.scopes else [],
                expires_at=int(row.expires_at.timestamp()) if row.expires_at else None,
            )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        original = set(refresh_token.scopes)
        if scopes and not set(scopes).issubset(original):
            raise TokenError("invalid_scope", "Requested scopes exceed the refresh token's scopes.")
        granted = scopes or refresh_token.scopes
        with SessionLocal() as db:
            row = db.get(OAuthRefreshToken, _hash(refresh_token.token))
            if not row:
                raise TokenError("invalid_grant", "Refresh token not found.")
            user_email = row.user_email
            db.delete(row)  # rotate: invalidate old
            db.commit()
        return self._issue_tokens(client.client_id, user_email, granted)

    # ── Access-token verification (stateless JWT) ────────────────────────────
    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        except JWTError:
            return None
        if payload.get("typ") != "mcp_access" or not payload.get("sub"):
            return None
        return AccessToken(
            token=token,
            client_id=payload.get("client_id", ""),
            scopes=(payload.get("scope") or "").split(),
            expires_at=payload.get("exp"),
            claims={"sub": payload["sub"]},
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await self.load_access_token(token)

    async def revoke_token(self, token) -> None:
        # Access tokens are stateless JWTs (can't revoke; short-lived). Refresh tokens delete.
        if isinstance(token, RefreshToken):
            with SessionLocal() as db:
                row = db.get(OAuthRefreshToken, _hash(token.token))
                if row:
                    db.delete(row)
                    db.commit()

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _issue_tokens(self, client_id: str, user_email: str, scopes: list[str]) -> OAuthToken:
        access = issue_access_token(user_email, client_id, scopes)
        refresh = "skbr_" + secrets.token_urlsafe(32)
        with SessionLocal() as db:
            db.add(OAuthRefreshToken(
                token_hash=_hash(refresh),
                client_id=client_id,
                user_email=user_email,
                scopes=" ".join(scopes),
                expires_at=_now() + timedelta(seconds=REFRESH_TTL_SECONDS),
            ))
            db.commit()
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL_SECONDS,
            refresh_token=refresh,
            scope=" ".join(scopes),
        )
