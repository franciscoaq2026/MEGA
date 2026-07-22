import os
import tempfile

os.environ["MEGASENA_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_auth.db")
os.environ["MEGASENA_AUTOSEED"] = "0"
os.environ["ALLOWED_EMAILS"] = "dono@example.com, backup@example.com"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402


@pytest.fixture(autouse=True)
def _fake_email(monkeypatch):
    """Não envia e-mail de verdade nos testes; finge que o envio deu certo."""
    monkeypatch.setattr(auth_router, "enviar_email", lambda *a, **k: True)


def make_client() -> TestClient:
    return TestClient(app)


def _login(c: TestClient, email: str = "dono@example.com") -> str:
    """Simula o fluxo do magic link e retorna o session_id."""
    r = c.post("/api/auth/request-link", json={"email": email})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    token = db._query("SELECT token FROM login_tokens ORDER BY rowid DESC LIMIT 1")[0]["token"]
    r = c.post("/api/auth/verify", json={"token": token})
    assert r.json()["status"] == "success"
    return r.json()["session_id"]


def test_email_nao_permitido_nao_cria_token():
    with make_client() as c:
        antes = db._query("SELECT COUNT(*) AS n FROM login_tokens")[0]["n"]
        r = c.post("/api/auth/request-link", json={"email": "intruso@x.com"})
        assert r.status_code == 200 and r.json()["status"] == "ok"  # resposta genérica
        depois = db._query("SELECT COUNT(*) AS n FROM login_tokens")[0]["n"]
        assert depois == antes  # nenhum token criado para e-mail não permitido


def test_token_uso_unico_e_sessao():
    with make_client() as c:
        r = c.post("/api/auth/request-link", json={"email": "dono@example.com"})
        assert r.json()["status"] == "ok"
        token = db._query("SELECT token FROM login_tokens ORDER BY rowid DESC LIMIT 1")[0]["token"]
        r = c.post("/api/auth/verify", json={"token": token})
        assert r.json()["status"] == "success"
        sid = r.json()["session_id"]
        # reutilizar o mesmo token falha
        assert c.post("/api/auth/verify", json={"token": token}).json()["status"] == "error"
        # sessão válida
        assert c.get("/api/auth/me", headers={"X-Session-Id": sid}).json()["status"] == "valid"


def test_bets_exigem_sessao():
    with make_client() as c:
        assert c.get("/api/bets").status_code == 401
        assert c.post("/api/bets", json={"concurso": 1, "origem": "manual", "dezenas": [1, 2, 3, 4, 5, 6]}).status_code == 401


def test_bets_crud_e_sync():
    with make_client() as c:
        sid = _login(c)
        h = {"X-Session-Id": sid}

        assert c.get("/api/bets", headers=h).json()["bets"] == []

        # sync (migração) com ids fixos
        payload = {
            "bets": [
                {"id": "a1", "concurso": 2700, "origem": "manual", "dezenas": [1, 2, 3, 4, 5, 6]},
                {"id": "a2", "concurso": 2700, "origem": "app", "dezenas": [10, 20, 30, 40, 50, 60]},
            ]
        }
        r = c.post("/api/bets/sync", json=payload, headers=h)
        assert {b["id"] for b in r.json()["bets"]} == {"a1", "a2"}

        # add gera id e persiste
        r = c.post("/api/bets", json={"concurso": 2701, "origem": "manual", "dezenas": [7, 8, 9, 10, 11, 12]}, headers=h)
        novo = r.json()["bet"]["id"]
        assert len(c.get("/api/bets", headers=h).json()["bets"]) == 3

        # delete
        assert c.delete(f"/api/bets/{novo}", headers=h).status_code == 200
        assert len(c.get("/api/bets", headers=h).json()["bets"]) == 2


def test_dois_emails_mesma_conta():
    """Os dois e-mails permitidos veem o mesmo histórico (recuperação)."""
    with make_client() as c:
        sid1 = _login(c, "dono@example.com")
        c.post("/api/bets", json={"concurso": 2702, "origem": "manual", "dezenas": [1, 2, 3, 4, 5, 6]}, headers={"X-Session-Id": sid1})

        sid2 = _login(c, "backup@example.com")
        bets = c.get("/api/bets", headers={"X-Session-Id": sid2}).json()["bets"]
        assert any(b["concurso"] == 2702 for b in bets)


def test_validacao_dezenas():
    with make_client() as c:
        sid = _login(c)
        h = {"X-Session-Id": sid}
        # dezenas repetidas
        assert c.post("/api/bets", json={"concurso": 1, "origem": "manual", "dezenas": [1, 1, 2, 3, 4, 5]}, headers=h).status_code == 422
        # origem inválida
        assert c.post("/api/bets", json={"concurso": 1, "origem": "x", "dezenas": [1, 2, 3, 4, 5, 6]}, headers=h).status_code == 422
