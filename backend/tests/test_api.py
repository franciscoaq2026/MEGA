import asyncio
import json
import os
import tempfile

os.environ["MEGASENA_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["MEGASENA_AUTOSEED"] = "0"  # testes começam com banco vazio

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, fetcher  # noqa: E402
from app.fetcher import FetchError, ler_espelho  # noqa: E402
from app.main import app  # noqa: E402

CSV = """concurso;data;dezena1;dezena2;dezena3;dezena4;dezena5;dezena6
1;11/03/1996;4;5;30;33;41;52
2;18/03/1996;9;37;39;41;43;49
3;25/03/1996;10;11;29;30;36;47
linha_invalida;xx;1;2;3;4;5;6
"""


def make_client() -> TestClient:
    return TestClient(app)


def test_health():
    with make_client() as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/health").status_code == 200  # sem prefixo (Vercel)


def test_import_csv_and_listing(sessao):
    with make_client() as c:
        r = c.post("/api/import-csv", files={"file": ("dados.csv", CSV, "text/csv")}, headers=sessao)
        assert r.status_code == 200
        body = r.json()
        assert body["imported"] == 3
        assert body["skipped"] == 1

        r = c.get("/api/draws?limit=10")
        assert r.json()["total"] == 3
        assert r.json()["items"][0]["concurso"] == 3  # ordem decrescente

        r = c.get("/api/draws/1")
        assert r.json()["dezenas"] == [4, 5, 30, 33, 41, 52]

        r = c.get("/api/status")
        assert r.json()["total_draws"] == 3
        assert r.json()["ultimo_local"]["concurso"] == 3


def test_sync_incremental(monkeypatch):
    """Servidor: histórico embutido + espelhos. Só entra o que falta — o que
    já está no banco (ex.: resultado oficial trazido pelo navegador) fica."""
    from app.routers import draws as draws_router

    espelho = [
        {"concurso": n, "data": f"2024-01-0{n}", "dezenas": sorted([n, n + 10, n + 20, n + 30, n + 40, n + 50])}
        for n in range(1, 6)
    ]

    async def fake_espelhos(loteria="mega"):
        return espelho, []

    monkeypatch.setattr(draws_router, "fetch_espelhos", fake_espelhos)
    monkeypatch.setattr(db, "load_bundled_seed", lambda loteria="mega": [])

    with make_client() as c:
        # 1..3 entraram pelo CSV do teste anterior, com dezenas diferentes
        antes = {n: db.get_draw(n)["dezenas"] for n in (1, 2, 3)}
        r = c.post("/api/sync")
        assert r.status_code == 200
        body = r.json()
        assert (body["latest_remote"], body["added"], body["remaining"]) == (5, 2, 0)
        assert db.count_draws() == 5
        assert {n: db.get_draw(n)["dezenas"] for n in (1, 2, 3)} == antes
        assert db.get_draw(5)["dezenas"] == espelho[4]["dezenas"]

        # segunda chamada: nada novo
        assert c.post("/api/sync").json()["added"] == 0

        # sem data/prêmio do espelho, o "próximo" sai do último concurso
        assert c.get("/api/status").json()["proximo"]["concurso"] == 6


def test_sync_em_lotes_junta_seed_e_espelho(monkeypatch):
    from app.routers import draws as draws_router

    seed = [{"concurso": n, "data": "2025-01-01", "dezenas": [1, 2, 3, 4, 5, n % 50 + 7]} for n in range(800, 804)]
    espelho = [{"concurso": n, "data": "2025-02-01", "dezenas": [1, 2, 3, 4, 5, 6]} for n in range(802, 806)]

    async def fake_espelhos(loteria="mega"):
        return espelho, ["espelho x: fora do ar"]

    monkeypatch.setattr(draws_router, "fetch_espelhos", fake_espelhos)
    monkeypatch.setattr(db, "load_bundled_seed", lambda loteria="mega": seed)
    with make_client() as c:
        r = c.post("/api/sync?max_batch=4").json()
        assert (r["added"], r["remaining"], r["latest_remote"]) == (4, 2, 805)
        assert r["errors"] == ["espelho x: fora do ar"]
        r = c.post("/api/sync?max_batch=4").json()
        assert (r["added"], r["remaining"]) == (2, 0)
        # no concurso em comum, vale o histórico embutido
        assert db.get_draw(802)["data"] == "2025-01-01"


def test_cron_sync(monkeypatch):
    from app.routers import draws as draws_router

    async def fake_espelhos(loteria="mega"):
        k = 6 if loteria == "mega" else 15
        return [{"concurso": 2999, "data": "2026-10-01", "dezenas": list(range(1, k + 1))}], []

    monkeypatch.setattr(draws_router, "fetch_espelhos", fake_espelhos)
    monkeypatch.setattr(db, "load_bundled_seed", lambda loteria="mega": [])
    monkeypatch.setenv("CRON_SECRET", "s3gredo")
    with make_client() as c:
        assert c.get("/api/cron/sync").status_code == 401
        assert c.get("/api/cron/sync", headers={"Authorization": "Bearer errado"}).status_code == 401
        r = c.get("/api/cron/sync", headers={"Authorization": "Bearer s3gredo"})
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"mega", "lofa"}
        assert body["mega"]["added"] == 1 and body["lofa"]["added"] == 1
        assert db.get_draw(2999, "mega") and db.get_draw(2999, "lofa")

        # sem CRON_SECRET o endpoint fica aberto (só acrescenta o que falta)
        monkeypatch.delenv("CRON_SECRET")
        assert c.get("/api/cron/sync").json()["mega"]["added"] == 0


def test_ler_espelho_formatos():
    eitchtee = [
        {"concurso": 7, "data": "20/10/2026", "resultado": ["02", "06", "09", "16", "31", "40"]},
        {"concurso": 8, "data": "22/10/2026", "resultado": ["02", "06"]},  # incompleto
    ]
    sorteios, invalidos = ler_espelho(eitchtee, "mega")
    assert sorteios == [{"concurso": 7, "data": "2026-10-20", "dezenas": [2, 6, 9, 16, 31, 40]}]
    assert invalidos == 1

    rjaugusto = {
        "historico": [
            {
                "numero": 3810,
                "dataApuracao": "21/10/2026",
                "dezenas": [1, 5, 6, 7, 10, 11, 14, 15, 16, 17, 18, 19, 20, 23, 24],
                "premiacoes": [],
            }
        ]
    }
    sorteios, invalidos = ler_espelho(rjaugusto, "lofa")
    assert (sorteios[0]["concurso"], sorteios[0]["data"], invalidos) == (3810, "2026-10-21", 0)

    with pytest.raises(FetchError):
        ler_espelho({"outra": "coisa"}, "mega")


def test_fetch_espelhos_descarta_concurso_divergente(monkeypatch):
    """Dois espelhos com dezenas diferentes no mesmo concurso: ele fica de
    fora (entra depois pela Caixa), e um espelho fora do ar não derruba o outro."""
    lofa = list(range(1, 16))
    outra = list(range(2, 17))
    eitchtee = [
        {"concurso": 1, "data": "01/01/2026", "resultado": lofa},
        {"concurso": 2, "data": "02/01/2026", "resultado": lofa},
    ]
    rjaugusto = {
        "historico": [
            {"numero": 2, "dataApuracao": "02/01/2026", "dezenas": outra},
            {"numero": 3, "dataApuracao": "03/01/2026", "dezenas": lofa},
        ]
    }

    def responder(req):
        return httpx.Response(200, json=eitchtee if "eitchtee" in str(req.url) else rjaugusto)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        fetcher.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(responder))
    )
    fetcher._cache_espelhos.clear()
    try:
        sorteios, avisos = asyncio.run(fetcher.fetch_espelhos("lofa"))
        assert [s["concurso"] for s in sorteios] == [1, 3]
        assert any("divergem" in a for a in avisos)

        def mega_fora(req):
            return httpx.Response(503)

        monkeypatch.setattr(
            fetcher.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(mega_fora))
        )
        sorteios, avisos = asyncio.run(fetcher.fetch_espelhos("mega"))
        assert sorteios == [] and "eitchtee" in avisos[0]
    finally:
        fetcher._cache_espelhos.clear()


def test_gravar_resultado_exige_login():
    """Sem sessão, ninguém grava resultado — senão um payload falso
    sobrescreveria o oficial e estragaria a conferência."""
    with make_client() as c:
        corpo = {"payloads": [{"numero": 1}]}
        assert c.post("/api/import-payloads", json=corpo).status_code == 401
        assert c.post("/api/import-payloads", json=corpo, headers={"X-Session-Id": "inventada"}).status_code == 401
        assert c.post("/api/import-csv", files={"file": ("x.csv", CSV, "text/csv")}).status_code == 401


def test_import_payloads_formato_caixa(sessao):
    """O navegador do usuário envia payloads brutos no formato da Caixa."""
    payload = {
        "numero": 3050,
        "dataApuracao": "10/07/2026",
        "listaDezenas": ["05", "12", "23", "34", "45", "56"],
        "numeroConcursoProximo": 3051,
        "dataProximoConcurso": "12/07/2026",
        "valorEstimadoProximoConcurso": 40000000,
        "acumulado": True,
    }
    invalido = {"numero": None, "listaDezenas": ["1", "2"]}
    with make_client() as c:
        r = c.post("/api/import-payloads", json={"payloads": [payload, invalido]}, headers=sessao)
        assert r.status_code == 200
        body = r.json()
        assert body["added"] == 1
        assert body["skipped"] == 1

        st = c.get("/api/status").json()
        assert st["ultimo_local"]["concurso"] == 3050
        assert st["ultimo_local"]["dezenas"] == [5, 12, 23, 34, 45, 56]
        assert st["proximo"]["concurso"] == 3051

        # payload mais antigo que o último não sobrescreve o meta "proximo"
        antigo = dict(payload, numero=3040, numeroConcursoProximo=3041)
        c.post("/api/import-payloads", json={"payloads": [antigo]}, headers=sessao)
        assert c.get("/api/status").json()["proximo"]["concurso"] == 3051

        # só payloads inválidos -> 400
        r = c.post("/api/import-payloads", json={"payloads": [invalido]}, headers=sessao)
        assert r.status_code == 400


def test_acertos_esperados_endpoint():
    """Régua de acertos por loteria — não depende do cache de sorteios, é só
    matemática do formato da aposta."""
    with make_client() as c:
        r = c.get("/api/acertos-esperados?loteria=lofa")
        assert r.status_code == 200
        body = r.json()
        assert body["dezenas"] == 15  # aposta simples da Lotofácil
        assert body["esperado"] == 9.0
        assert body["menor_faixa_premiada"] == 11
        assert body["premiado"]["one_in"] == 9

        assert c.get("/api/acertos-esperados?loteria=lofa&dezenas=18").json()["esperado"] == 10.8
        assert c.get("/api/acertos-esperados").json()["esperado"] == 0.6  # Mega
        # fora do que a Caixa aceita
        assert c.get("/api/acertos-esperados?loteria=lofa&dezenas=21").status_code == 400


def test_backtest_varios_jogos_e_janelas():
    """A tela pede 50/100/200 concursos e 1 a 5 jogos por concurso. Depois da
    primeira simulação, janelas e lotes menores saem dela — e dão o mesmo que
    simular de novo."""
    import random

    from app import checker

    draws = [
        {"concurso": i, "data": f"2024-01-{i % 28 + 1:02d}",
         "dezenas": sorted(random.Random(i).sample(range(1, 26), 15))}
        for i in range(1, 161)
    ]
    db.init_db()
    db.upsert_draws(draws, "lofa")
    with make_client() as c:
        r = c.post("/api/backtest?loteria=lofa&ultimos=100&jogos=3&espalhar=true")
        assert r.status_code == 200
        body = r.json()
        assert (body["concursos_simulados"], body["jogos_por_concurso"], body["espalhar"]) == (100, 3, True)
        assert [j["concursos"] for j in body["acaso"]["janelas"]] == [50, 100, 200]

        menor = c.post("/api/backtest?loteria=lofa&ultimos=50&jogos=2&espalhar=true").json()
        # o banco é dividido com outros testes: o histórico é o que está nele
        historico = db.get_all_draws_asc("lofa")
        direto = checker.backtest(historico, ultimos=50, loteria="lofa", jogos=2, espalhar=True)
        assert menor == json.loads(json.dumps(direto))

        assert c.post("/api/backtest?loteria=lofa&ultimos=50&jogos=6").status_code == 422
