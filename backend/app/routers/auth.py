"""Endpoints de login sem senha (magic link) para uso pessoal restrito."""

import os
import uuid
from datetime import timedelta

import re

from fastapi import APIRouter, Header
from pydantic import BaseModel, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

from .. import auth, db
from ..auth import _agora
from ..email_sender import enviar_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _app_url() -> str:
    url = os.environ.get("APP_URL")
    if url:
        return url.rstrip("/")
    prod = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")
    if prod:
        return f"https://{prod}"
    return "http://localhost:5173"


class RequestLink(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("e-mail inválido")
        return v


class VerifyToken(BaseModel):
    token: str


class LogoutBody(BaseModel):
    session_id: str


# Resposta genérica: nunca revela se um e-mail está ou não cadastrado.
_OK_GENERICO = {
    "status": "ok",
    "message": "Se este e-mail tiver acesso, você receberá um link para entrar.",
}


@router.post("/request-link")
def request_link(body: RequestLink):
    email = auth.normalizar_email(body.email)
    if not auth.email_permitido(email):
        return _OK_GENERICO
    token = uuid.uuid4().hex.upper()
    expires = (_agora() + timedelta(seconds=auth.TOKEN_TTL_SECONDS)).isoformat()
    db.create_login_token(token, email, expires)
    link = f"{_app_url()}/?login_token={token}"
    html = (
        "<p>Seu link de acesso ao <b>Mega-Sena Stats</b> (válido por 30 min):</p>"
        f'<p><a href="{link}" style="background:#16a34a;color:#fff;padding:10px 20px;'
        'border-radius:6px;text-decoration:none">Entrar agora</a></p>'
        f'<p style="font-size:12px;color:#666">Ou copie e cole no navegador: {link}</p>'
    )
    enviado = enviar_email(email, "Seu link de acesso — Mega-Sena Stats", html)
    if not enviado:
        return {
            "status": "error",
            "message": "Falha ao enviar o e-mail de acesso. Tente novamente em instantes.",
        }
    return _OK_GENERICO


@router.post("/verify")
def verify(body: VerifyToken):
    rec = db.get_login_token(body.token)
    if not rec or rec["used"]:
        return {"status": "error", "message": "Link inválido ou já utilizado. Solicite um novo."}
    try:
        expirado = _agora() > auth._parse(rec["expires_at"])
    except (ValueError, KeyError):
        expirado = True
    if expirado:
        return {"status": "error", "message": "Link expirado. Solicite um novo."}

    email = auth.normalizar_email(rec["email"])
    if not auth.email_permitido(email):
        return {"status": "error", "message": "Este e-mail não tem mais acesso."}

    db.consume_login_token(body.token)
    session_id = uuid.uuid4().hex
    now = _agora()
    expires = now + timedelta(seconds=auth.SESSION_TTL_SECONDS)
    account_id = auth.account_do_email(email)
    db.create_session(session_id, email, account_id, now.isoformat(), expires.isoformat())
    return {
        "status": "success",
        "session_id": session_id,
        "email": email,
        "expires_at": expires.isoformat(),
    }


@router.get("/me")
def me(x_session_id: str | None = Header(default=None)):
    sessao = auth.validar_sessao(x_session_id)
    if not sessao:
        return {"status": "none"}
    return {"status": "valid", "email": sessao["email"]}


@router.post("/logout")
def logout(body: LogoutBody):
    db.delete_session(body.session_id)
    return {"status": "success"}
