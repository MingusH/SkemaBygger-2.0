"""Browser-facing login/consent page for the OAuth authorization flow.

DBOAuthProvider.authorize() redirects the user's browser here with the authorization
request encoded in a signed `req` JWT. The user logs in with their existing SkemaBygger
email/password; on success we mint an authorization code bound to that user and redirect
back to the OAuth client's redirect_uri."""
from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from mcp.server.auth.provider import construct_redirect_uri

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.routers.auth import verify_password
from app.services.oauth_provider import create_auth_code

router = APIRouter(prefix="/oauth", tags=["oauth"])


def _page(req: str, error: str = "") -> str:
    err = f'<p style="color:#dc2626;font-size:13px;margin:0 0 12px">{error}</p>' if error else ""
    return f"""<!doctype html><html lang=da><head><meta charset=utf-8>
<title>SkemaBygger – Log ind</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
 body{{font-family:system-ui,Segoe UI,sans-serif;background:#f9fafb;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
 .card{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:28px;width:320px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
 h1{{font-size:18px;margin:0 0 4px;color:#1d4ed8}} p.sub{{color:#6b7280;font-size:13px;margin:0 0 18px}}
 label{{font-size:12px;color:#6b7280;display:block;margin-bottom:4px}}
 input{{width:100%;box-sizing:border-box;border:1px solid #d1d5db;border-radius:8px;padding:9px;margin-bottom:14px;font-size:14px}}
 button{{width:100%;background:#2563eb;color:#fff;border:0;border-radius:8px;padding:10px;font-size:14px;cursor:pointer}}
</style></head><body>
<form class=card method=post action="/oauth/login">
 <h1>SkemaBygger</h1>
 <p class=sub>Log ind for at give AI-assistenten adgang til dine skoler.</p>
 {err}
 <input type=hidden name=req value="{req}">
 <label>Email</label><input name=email type=email autofocus required>
 <label>Adgangskode</label><input name=password type=password required>
 <button type=submit>Log ind og forbind</button>
</form></body></html>"""


def _decode_req(req: str) -> dict | None:
    try:
        payload = jwt.decode(req, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    return payload if payload.get("typ") == "mcp_authreq" else None


@router.get("/login", response_class=HTMLResponse)
def login_form(req: str):
    if _decode_req(req) is None:
        return HTMLResponse(_page("", "Ugyldig eller udløbet forespørgsel. Start forbindelsen forfra i din klient."), status_code=400)
    return HTMLResponse(_page(req))


@router.post("/login")
def login_submit(req: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    payload = _decode_req(req)
    if payload is None:
        return HTMLResponse(_page("", "Ugyldig eller udløbet forespørgsel. Start forbindelsen forfra i din klient."), status_code=400)

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_password(password, user.hashed_password):
        return HTMLResponse(_page(req, "Forkert email eller adgangskode."), status_code=401)

    code = create_auth_code(
        client_id=payload["client_id"],
        user_email=user.email,
        redirect_uri=payload["redirect_uri"],
        redirect_uri_provided_explicitly=payload.get("redirect_uri_provided_explicitly", True),
        scopes=payload.get("scopes") or [],
        code_challenge=payload.get("code_challenge"),
    )
    target = construct_redirect_uri(payload["redirect_uri"], code=code, state=payload.get("state"))
    return RedirectResponse(target, status_code=302)
