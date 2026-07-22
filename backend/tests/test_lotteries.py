import json
import os
import tempfile

os.environ["MEGASENA_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_lot.db")
os.environ["MEGASENA_AUTOSEED"] = "0"
# Superset alinhado aos outros arquivos de teste: como as variáveis de ambiente
# são globais no processo do pytest, todos os arquivos devem concordar nelas.
os.environ["ALLOWED_EMAILS"] = "dono@example.com, backup@example.com"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, lotteries  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402


@pytest.fixture(autouse=True)
def _fake_email(monkeypatch):
    monkeypatch.setattr(auth_router, "enviar_email", lambda *a, **k: True)


def make_client() -> TestClient:
    return TestClient(app)


def _login(c: TestClient) -> str:
    c.post("/api/auth/request-link", json={"email": "dono@example.com"})
    token = db._query("SELECT token FROM login_tokens ORDER BY rowid DESC LIMIT 1")[0]["token"]
    return c.post("/api/auth/verify", json={"token": token}).json()["session_id"]


def test_registro_loterias():
    assert lotteries.get_loteria("loto")["nome"] == "Lotomania"
    assert lotteries.get_loteria("loto")["sorteadas"] == 20
    assert lotteries.get_loteria(None)["code"] == "mega"  # padrão
    assert lotteries.get_loteria("xyz")["code"] == "mega"  # inválido cai na Mega
    assert 0 in lotteries.get_loteria("loto")["faixas"]  # 0 acertos premia


def test_draws_genericos_isolados_por_loteria():
    with make_client():
        # concurso único para não colidir com dados de outros arquivos de teste
        cc = 990100
        antes_mega = db.count_draws("mega")
        antes_loto = db.count_draws("loto")
        db.upsert_draws([{"concurso": cc, "data": "2026-01-01", "dezenas": [1, 2, 3, 4, 5, 6]}], "mega")
        db.upsert_draws([{"concurso": cc, "data": "2026-01-02", "dezenas": list(range(0, 20))}], "loto")
        # mesmo número de concurso, loterias diferentes, sem colisão
        assert db.count_draws("mega") == antes_mega + 1
        assert db.count_draws("loto") == antes_loto + 1
        assert db.get_draw(cc, "mega")["dezenas"] == [1, 2, 3, 4, 5, 6]
        assert db.get_draw(cc, "loto")["dezenas"] == list(range(0, 20))
        # default é mega
        assert db.get_draw(cc)["dezenas"] == [1, 2, 3, 4, 5, 6]


def test_migracao_legada_draws_para_generica():
    with make_client():
        # simula banco antigo: linha na tabela legada `draws`
        db._write(
            [(
                "INSERT OR REPLACE INTO draws (concurso, data, d1, d2, d3, d4, d5, d6) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (9999, "1996-03-11", 4, 5, 30, 33, 41, 52),
            )]
        )
        # apaga a versão genérica desse concurso para forçar a migração
        db._write([("DELETE FROM lottery_draws WHERE loteria='mega' AND concurso=9999", ())])
        # zera o marcador rodando a migração só se genérica de mega estiver vazia:
        db._write([("DELETE FROM lottery_draws WHERE loteria='mega'", ())])
        db._migrate_legacy_draws()
        got = db.get_draw(9999, "mega")
        assert got is not None
        assert got["dezenas"] == [4, 5, 30, 33, 41, 52]


def test_aposta_lotomania_via_api():
    with make_client() as c:
        sid = _login(c)
        h = {"X-Session-Id": sid}
        cc_loto, cc_mega = 990290, 990280  # concursos únicos p/ isolamento
        dezenas_loto = list(range(0, 50))  # 50 dezenas de 00 a 49

        # aposta de Lotomania válida
        r = c.post("/api/bets", json={"loteria": "loto", "concurso": cc_loto, "origem": "manual", "dezenas": dezenas_loto}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["bet"]["loteria"] == "loto"

        # aposta de Mega válida (6 dezenas)
        c.post("/api/bets", json={"loteria": "mega", "concurso": cc_mega, "origem": "manual", "dezenas": [1, 2, 3, 4, 5, 6]}, headers=h)

        # filtro por loteria (isolando pelos concursos únicos deste teste)
        loto = [b for b in c.get("/api/bets?loteria=loto", headers=h).json()["bets"] if b["concurso"] == cc_loto]
        mega = [b for b in c.get("/api/bets?loteria=mega", headers=h).json()["bets"] if b["concurso"] == cc_mega]
        todas = c.get("/api/bets", headers=h).json()["bets"]
        assert len(loto) == 1 and loto[0]["loteria"] == "loto"
        assert len(mega) == 1 and mega[0]["loteria"] == "mega"
        # o filtro loto não traz a aposta mega
        assert all(b["loteria"] == "loto" for b in c.get("/api/bets?loteria=loto", headers=h).json()["bets"])
        assert {cc_loto, cc_mega}.issubset({b["concurso"] for b in todas})


def test_validacao_dezenas_por_loteria():
    with make_client() as c:
        sid = _login(c)
        h = {"X-Session-Id": sid}
        # Lotomania com número fora do intervalo (100)
        r = c.post("/api/bets", json={"loteria": "loto", "concurso": 1, "origem": "manual", "dezenas": list(range(1, 50)) + [100]}, headers=h)
        assert r.status_code == 422
        # Lotomania com menos de 50 dezenas
        r = c.post("/api/bets", json={"loteria": "loto", "concurso": 1, "origem": "manual", "dezenas": [1, 2, 3]}, headers=h)
        assert r.status_code == 422
        # Mega com 61 (fora do intervalo)
        r = c.post("/api/bets", json={"loteria": "mega", "concurso": 1, "origem": "manual", "dezenas": [1, 2, 3, 4, 5, 61]}, headers=h)
        assert r.status_code == 422
