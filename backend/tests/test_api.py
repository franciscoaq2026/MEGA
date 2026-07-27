import os
import tempfile

os.environ["MEGASENA_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["MEGASENA_AUTOSEED"] = "0"  # testes começam com banco vazio

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
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


def test_import_csv_and_listing():
    with make_client() as c:
        r = c.post("/api/import-csv", files={"file": ("dados.csv", CSV, "text/csv")})
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
    """Simula o remoto com 5 concursos: o sync deve buscar só os que faltam."""
    from app.routers import draws as draws_router

    fake = {
        n: {
            "concurso": n,
            "data": f"2024-01-0{n}",
            "dezenas": sorted([n, n + 10, n + 20, n + 30, n + 40, n + 50]),
            "proximo": {"concurso": 6, "data": "2024-02-01", "estimativa": 1000000, "acumulado": True},
        }
        for n in range(1, 6)
    }

    async def fake_latest(loteria="mega"):
        return fake[5]

    async def fake_many(nums, loteria="mega", concurrency=8):
        return [fake[n] for n in nums], []

    monkeypatch.setattr(draws_router, "fetch_latest", fake_latest)
    monkeypatch.setattr(draws_router, "fetch_many", fake_many)

    with make_client() as c:
        before = db.count_draws()
        r = c.post("/api/sync")
        assert r.status_code == 200
        body = r.json()
        assert body["latest_remote"] == 5
        assert body["remaining"] == 0
        assert db.count_draws() == 5
        assert db.count_draws() >= before

        # segunda chamada: nada novo a baixar
        r = c.post("/api/sync")
        assert r.json()["added"] == 0

        # status agora tem o "próximo concurso" vindo da API
        st = c.get("/api/status").json()
        assert st["proximo"]["concurso"] == 6


def test_import_payloads_formato_caixa():
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
        r = c.post("/api/import-payloads", json={"payloads": [payload, invalido]})
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
        c.post("/api/import-payloads", json={"payloads": [antigo]})
        assert c.get("/api/status").json()["proximo"]["concurso"] == 3051

        # só payloads inválidos -> 400
        r = c.post("/api/import-payloads", json={"payloads": [invalido]})
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
