"""Envio de e-mail via Google Apps Script (grátis, sem domínio próprio).

O Apps Script é um web app publicado na conta Google do dono que recebe
{to, subject, html} por POST e dispara o e-mail pelo próprio Gmail. A URL do
script fica na variável de ambiente GOOGLE_SCRIPT_URL.

O código do script está em docs/apps-script-email.gs.
"""

import os

import httpx


def script_url() -> str | None:
    return os.environ.get("GOOGLE_SCRIPT_URL")


def enviar_email(to: str, subject: str, html: str) -> bool:
    """Envia um e-mail e informa se deu certo (não levanta exceção)."""
    url = script_url()
    if not url:
        print("[email] GOOGLE_SCRIPT_URL não configurada — e-mail não enviado")
        return False
    try:
        resp = httpx.post(
            url,
            json={"to": to, "subject": subject, "html": html},
            timeout=15.0,
            follow_redirects=True,
        )
        if resp.status_code >= 400:
            print(f"[email] Apps Script HTTP {resp.status_code} para {to}")
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - falha de rede não deve quebrar a API
        print(f"[email] falha ao enviar para {to}: {exc}")
        return False
