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


def test_espalhar_gravado_por_jogo():
    """true/false voltam como foram salvos; ausente vira None (não se aplica)."""
    with make_client() as c:
        h = {"X-Session-Id": _login(c)}
        base = {"concurso": 2800, "origem": "app", "estrategia": "aleatorio"}
        c.post("/api/bets", json={**base, "id": "e1", "espalhar": True, "dezenas": [1, 2, 3, 4, 5, 6]}, headers=h)
        c.post("/api/bets", json={**base, "id": "e2", "espalhar": False, "dezenas": [7, 8, 9, 10, 11, 12]}, headers=h)
        c.post("/api/bets", json={**base, "id": "e3", "dezenas": [13, 14, 15, 16, 17, 18]}, headers=h)
        # o sync (caminho do celular/computador) preserva o campo
        c.post(
            "/api/bets/sync",
            json={"bets": [{**base, "id": "e4", "espalhar": False, "dezenas": [19, 20, 21, 22, 23, 24]}]},
            headers=h,
        )
        por_id = {b["id"]: b["espalhar"] for b in c.get("/api/bets", headers=h).json()["bets"]}
        assert (por_id["e1"], por_id["e2"], por_id["e3"], por_id["e4"]) == (True, False, None, False)


def test_migracao_adiciona_coluna_espalhar(tmp_path, monkeypatch):
    """Banco criado antes do campo: a coluna entra no init e os jogos antigos
    continuam lá, com espalhar = None."""
    import sqlite3

    caminho = tmp_path / "antigo.db"
    con = sqlite3.connect(caminho)
    con.execute(
        "CREATE TABLE bets (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, "
        "loteria TEXT NOT NULL DEFAULT 'mega', concurso INTEGER NOT NULL, origem TEXT NOT NULL, "
        "estrategia TEXT, dezenas TEXT NOT NULL, criado_em TEXT NOT NULL)"
    )
    con.execute(
        "INSERT INTO bets VALUES ('velho', 'owner', 'mega', 3000, 'app', 'aleatorio', '[1,2,3,4,5,6]', '')"
    )
    con.commit()
    con.close()

    monkeypatch.setattr(db, "DB_PATH", str(caminho))
    db.init_db()
    cols = {r["name"] for r in db._query("PRAGMA table_info(bets)")}
    assert "espalhar" in cols
    assert db.list_bets("owner")[0]["espalhar"] is None
    db.upsert_bet("owner", {"id": "novo", "concurso": 3001, "origem": "app", "dezenas": [1, 2, 3, 4, 5, 6], "espalhar": True})
    assert {b["id"]: b["espalhar"] for b in db.list_bets("owner")} == {"velho": None, "novo": True}
