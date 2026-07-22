"""Autenticação sem senha para uso pessoal restrito.

Modelo enxuto (não comercial): o acesso é liberado só para e-mails de uma
lista de permitidos (ALLOWED_EMAILS). Todos esses e-mails compartilham a
MESMA conta — assim o dono pode entrar por qualquer um dos seus e-mails e ver
o mesmo histórico (recuperação de acesso caso perca um deles).

Não há cadastro, senha ou papéis: quem está na lista entra por magic link;
quem não está simplesmente não recebe o link.
"""

import os
from datetime import datetime, timezone

from . import db

# Conta única compartilhada por todos os e-mails permitidos (uso pessoal).
ACCOUNT_ID = "owner"

# Validade da sessão e do token do magic link.
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 dias
TOKEN_TTL_SECONDS = 30 * 60  # 30 minutos


def allowed_emails() -> set[str]:
    """E-mails autorizados (variável de ambiente, separados por vírgula).

    Padrão: gilcelio@gmail.com. Para adicionar um e-mail de backup, basta
    definir ALLOWED_EMAILS no Vercel — sem alterar o código.
    """
    raw = os.environ.get("ALLOWED_EMAILS", "gilcelio@gmail.com")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def email_permitido(email: str) -> bool:
    return normalizar_email(email) in allowed_emails()


def account_do_email(email: str) -> str:
    """Todos os e-mails permitidos apontam para a mesma conta."""
    return ACCOUNT_ID


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _parse(dt: str) -> datetime:
    d = datetime.fromisoformat(dt)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def validar_sessao(session_id: str | None) -> dict | None:
    """Retorna a sessão válida ({id, email, account_id, ...}) ou None."""
    if not session_id:
        return None
    sessao = db.get_session(session_id)
    if not sessao:
        return None
    try:
        if _agora() > _parse(sessao["expires_at"]):
            db.delete_session(session_id)
            return None
    except (ValueError, KeyError):
        return None
    return sessao
