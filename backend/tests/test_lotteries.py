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

# Sorteio de Lotofácil válido (15 dezenas de 1 a 25) reutilizado nos testes.
LOFA_15 = list(range(1, 16))


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
    lofa = lotteries.get_loteria("lofa")
    assert lofa["nome"] == "Lotofácil"
    assert lofa["sorteadas"] == 15 and lofa["escolher"] == 15
    assert lofa["min_num"] == 1 and lofa["max_num"] == 25
    assert set(lofa["faixas"]) == {15, 14, 13, 12, 11}
    assert lotteries.get_loteria(None)["code"] == "mega"  # padrão
    assert lotteries.get_loteria("xyz")["code"] == "mega"  # inválido cai na Mega
    # a Lotomania foi removida do site: seu código cai no padrão
    assert lotteries.get_loteria("loto")["code"] == "mega"
    assert not lotteries.is_valid("loto")


def test_helpers_de_config():
    lofa = lotteries.get_loteria("lofa")
    mega = lotteries.get_loteria("mega")
    assert lotteries.numbers(lofa) == list(range(1, 26))
    assert lotteries.linhas(lofa) == 5 and lotteries.linhas(mega) == 6
    assert lotteries.faixa_maxima(lofa) == 15 and lotteries.faixa_maxima(mega) == 6


def test_draws_genericos_isolados_por_loteria():
    with make_client():
        # concurso único para não colidir com dados de outros arquivos de teste
        cc = 990100
        antes_mega = db.count_draws("mega")
        antes_lofa = db.count_draws("lofa")
        db.upsert_draws([{"concurso": cc, "data": "2026-01-01", "dezenas": [1, 2, 3, 4, 5, 6]}], "mega")
        db.upsert_draws([{"concurso": cc, "data": "2026-01-02", "dezenas": LOFA_15}], "lofa")
        # mesmo número de concurso, loterias diferentes, sem colisão
        assert db.count_draws("mega") == antes_mega + 1
        assert db.count_draws("lofa") == antes_lofa + 1
        assert db.get_draw(cc, "mega")["dezenas"] == [1, 2, 3, 4, 5, 6]
        assert db.get_draw(cc, "lofa")["dezenas"] == LOFA_15
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


def test_aposta_lotofacil_via_api():
    with make_client() as c:
        sid = _login(c)
        h = {"X-Session-Id": sid}
        cc_lofa, cc_mega = 990290, 990280  # concursos únicos p/ isolamento

        r = c.post("/api/bets", json={"loteria": "lofa", "concurso": cc_lofa, "origem": "manual", "dezenas": LOFA_15}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["bet"]["loteria"] == "lofa"

        # aposta de Mega válida (6 dezenas)
        c.post("/api/bets", json={"loteria": "mega", "concurso": cc_mega, "origem": "manual", "dezenas": [1, 2, 3, 4, 5, 6]}, headers=h)

        # filtro por loteria (isolando pelos concursos únicos deste teste)
        lofa = [b for b in c.get("/api/bets?loteria=lofa", headers=h).json()["bets"] if b["concurso"] == cc_lofa]
        mega = [b for b in c.get("/api/bets?loteria=mega", headers=h).json()["bets"] if b["concurso"] == cc_mega]
        todas = c.get("/api/bets", headers=h).json()["bets"]
        assert len(lofa) == 1 and lofa[0]["loteria"] == "lofa"
        assert len(mega) == 1 and mega[0]["loteria"] == "mega"
        assert all(b["loteria"] == "lofa" for b in c.get("/api/bets?loteria=lofa", headers=h).json()["bets"])
        assert {cc_lofa, cc_mega}.issubset({b["concurso"] for b in todas})


def test_aposta_lotofacil_ate_20_dezenas():
    """A Caixa aceita de 15 a 20 dezenas na Lotofácil."""
    with make_client() as c:
        sid = _login(c)
        h = {"X-Session-Id": sid}
        r = c.post("/api/bets", json={"loteria": "lofa", "concurso": 990291, "origem": "manual", "dezenas": list(range(1, 21))}, headers=h)
        assert r.status_code == 200, r.text
        # 21 dezenas passa do limite
        r = c.post("/api/bets", json={"loteria": "lofa", "concurso": 990292, "origem": "manual", "dezenas": list(range(1, 22))}, headers=h)
        assert r.status_code == 422


def test_generate_lotofacil():
    with make_client() as c:
        r = c.post("/api/generate?loteria=lofa", json={"estrategia": "aleatorio", "jogos": 2})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dezenas"] == 15  # aposta simples da Lotofácil
        for j in body["jogos"]:
            assert len(j["dezenas"]) == 15
            assert all(1 <= n <= 25 for n in j["dezenas"])


def test_generate_lotofacil_18_dezenas():
    with make_client() as c:
        r = c.post("/api/generate?loteria=lofa", json={"estrategia": "aleatorio", "jogos": 1, "dezenas": 18})
        assert r.status_code == 200, r.text
        assert len(r.json()["jogos"][0]["dezenas"]) == 18
        # acima de 20 a Caixa não aceita
        r = c.post("/api/generate?loteria=lofa", json={"estrategia": "aleatorio", "jogos": 1, "dezenas": 22})
        assert r.status_code == 400


def test_todas_estrategias_funcionam_na_lotofacil():
    with make_client() as c:
        db.upsert_draws(
            [{"concurso": 993000 + i, "data": "2026-01-01",
              "dezenas": sorted(((n + i) % 25) + 1 for n in range(15))}
             for i in range(30)],
            "lofa",
        )
        for est in ("aleatorio", "frequencia", "atrasados", "balanceado"):
            r = c.post("/api/generate?loteria=lofa", json={"estrategia": est, "jogos": 1})
            assert r.status_code == 200, f"{est}: {r.text}"
            dz = r.json()["jogos"][0]["dezenas"]
            assert len(dz) == 15 and len(set(dz)) == 15
            assert all(1 <= n <= 25 for n in dz)


def test_check_lotofacil_faixas():
    with make_client() as c:
        db.upsert_draws(
            [{"concurso": 995001, "data": "2026-01-01", "dezenas": LOFA_15}], "lofa"
        )
        # 15 acertos (aposta idêntica ao sorteio) e 11 acertos (faixa mínima)
        onze = list(range(1, 12)) + [21, 22, 23, 24]
        r = c.post(
            "/api/check?loteria=lofa",
            json={"apostas": [
                {"concurso": 995001, "dezenas": LOFA_15},
                {"concurso": 995001, "dezenas": onze},
            ]},
        )
        assert r.status_code == 200, r.text
        cheio, minimo = r.json()["resultados"]
        assert cheio["acertos"] == 15 and cheio["faixa"] == "15 acertos"
        assert minimo["acertos"] == 11 and minimo["faixa"] == "11 acertos"


def test_check_lotofacil_dez_acertos_nao_premia():
    with make_client() as c:
        db.upsert_draws(
            [{"concurso": 995002, "data": "2026-01-01", "dezenas": LOFA_15}], "lofa"
        )
        dez = list(range(1, 11)) + [21, 22, 23, 24, 25]
        r = c.post("/api/check?loteria=lofa", json={"apostas": [{"concurso": 995002, "dezenas": dez}]})
        res = r.json()["resultados"][0]
        assert res["acertos"] == 10 and res["faixa"] is None


def test_import_payloads_lotofacil():
    with make_client() as c:
        payload = {
            "numero": 995500,
            "listaDezenas": [f"{n:02d}" for n in LOFA_15],
            "dataApuracao": "10/02/2026",
            "numeroConcursoProximo": 995501,
        }
        r = c.post("/api/import-payloads?loteria=lofa", json={"payloads": [payload]})
        assert r.status_code == 200, r.text
        assert r.json()["added"] == 1
        got = db.get_draw(995500, "lofa")
        assert got is not None and got["dezenas"] == LOFA_15


def test_import_payload_recusa_dezenas_invalidas():
    """Um payload de outra loteria (20 dezenas até 99) não entra como Lotofácil."""
    with make_client() as c:
        payload = {
            "numero": 995600,
            "listaDezenas": [f"{n:02d}" for n in range(0, 20)],
            "dataApuracao": "10/02/2026",
        }
        r = c.post("/api/import-payloads?loteria=lofa", json={"payloads": [payload]})
        assert r.status_code == 400


def test_stats_frequency_lotofacil_cobre_25_numeros():
    with make_client() as c:
        db.upsert_draws(
            [{"concurso": 996001, "data": "2026-01-01", "dezenas": LOFA_15}], "lofa"
        )
        r = c.get("/api/stats/frequency?loteria=lofa")
        assert r.status_code == 200, r.text
        assert len(r.json()["freq"]) == 25  # 1 a 25


def test_stats_avancadas_lotofacil_generalizadas():
    with make_client() as c:
        db.upsert_draws(
            [{"concurso": 997000 + i, "data": "2026-01-01",
              "dezenas": sorted(((n + i) % 25) + 1 for n in range(15))}
             for i in range(5)],
            "lofa",
        )
        # paridade: 16 faixas (0..15 pares) para 15 sorteadas
        par = c.get("/api/stats/parity?loteria=lofa")
        assert par.status_code == 200, par.text
        assert len(par.json()["rows"]) == 16
        assert par.json()["rows"][-1]["evens"] == 15
        # soma: média teórica = 15 * (1+25)/2 = 195
        s = c.get("/api/stats/sums?loteria=lofa")
        assert s.status_code == 200
        assert s.json()["theoretical_mean"] == 195.0
        # duplas
        pr = c.get("/api/stats/pairs?loteria=lofa")
        assert pr.status_code == 200 and "pairs" in pr.json()


def test_odds_lotofacil_bate_com_a_caixa():
    """Números oficiais publicados pela Caixa para a Lotofácil."""
    with make_client() as c:
        r = c.get("/api/odds?loteria=lofa")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dezenas"] == 15
        assert body["combos_simples"] == 1
        assert body["custo_estimado"] == 3.50
        assert body["faixas"]["15 acertos"]["one_in"] == 3_268_760
        assert body["faixas"]["11 acertos"]["one_in"] == 11

        # 18 dezenas: C(18,15) = 816 apostas simples -> R$ 2.856,00
        r18 = c.get("/api/odds?loteria=lofa&dezenas=18").json()
        assert r18["combos_simples"] == 816
        assert r18["custo_estimado"] == 2856.00
        # 1 em 4.006 — confere por dois caminhos independentes: a
        # hipergeométrica direta e "816 apostas simples em 3.268.760".
        assert r18["faixas"]["15 acertos"]["one_in"] == 4006
        assert round(3_268_760 / 816) == 4006

        # a Mega segue com os números dela
        rm = c.get("/api/odds?loteria=mega").json()
        assert rm["faixas"]["sena"]["one_in"] == 50_063_860
        assert rm["custo_estimado"] == 6.00


def test_fabrica_liberada_na_lotofacil():
    with make_client() as c:
        db.upsert_draws(
            [{"concurso": 994000 + i, "data": "2026-01-01",
              "dezenas": sorted(((n * 7 + i) % 25) + 1 for n in range(15))}
             for i in range(60)],
            "lofa",
        )
        # faixas históricas usam os indicadores da Lotofácil (miolo, sem consecutivos)
        rg = c.get("/api/analysis/ranges?loteria=lofa")
        assert rg.status_code == 200, rg.text
        chaves = set(rg.json()["ranges"])
        assert "miolo" in chaves and "consecutivos" not in chaves
        assert rg.json()["ranges"]["baixas"]["label"] == "Dezenas baixas (1–13)"

        # gerador avançado
        ga = c.post("/api/generate-advanced?loteria=lofa", json={"jogos": 2})
        assert ga.status_code == 200, ga.text
        for j in ga.json()["jogos"]:
            assert len(j["dezenas"]) == 15

        # termômetro
        sc = c.post("/api/score?loteria=lofa", json={"dezenas": LOFA_15})
        assert sc.status_code == 200, sc.text
        assert 0 <= sc.json()["nota"] <= 100

        # raio-x (antes bloqueado fora da Mega)
        xr = c.get("/api/stats/xray/994005?loteria=lofa")
        assert xr.status_code == 200, xr.text
        assert len(xr.json()["hot6"]) == 15  # acompanha a aposta simples


def test_fechamento_lotofacil():
    with make_client() as c:
        # roda completa de 17 dezenas = C(17,15) = 136 jogos
        r = c.post("/api/wheel?loteria=lofa", json={"dezenas": list(range(1, 18)), "tipo": "completa"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["num_jogos"] == 136
        assert body["custo_estimado"] == round(136 * 3.50, 2)

        # 18 dezenas estoura o limite da completa, mas cabe no reduzido
        r = c.post("/api/wheel?loteria=lofa", json={"dezenas": list(range(1, 19)), "tipo": "completa"})
        assert r.status_code == 400
        r = c.post("/api/wheel?loteria=lofa", json={"dezenas": list(range(1, 19)), "tipo": "reduzida", "garantia": 14})
        assert r.status_code == 200, r.text
        red = r.json()
        assert red["num_jogos"] < red["num_jogos_roda_completa"]
        assert red["garantia_faixa"] == "14 acertos"

        # garantia inválida para a Lotofácil (4 é faixa da Mega)
        r = c.post("/api/wheel?loteria=lofa", json={"dezenas": list(range(1, 18)), "tipo": "reduzida", "garantia": 4})
        assert r.status_code == 400

        # fechamento exige MAIS que a aposta simples
        r = c.post("/api/wheel?loteria=lofa", json={"dezenas": LOFA_15, "tipo": "reduzida"})
        assert r.status_code == 400


def test_odds_table_lotofacil():
    """Tabela mestra da aba Probabilidades, com os números oficiais da Caixa."""
    with make_client() as c:
        t = c.get("/api/odds/table?loteria=lofa")
        assert t.status_code == 200, t.text
        body = t.json()
        assert body["premios_fixos"] == {"11": 7.0, "12": 14.0, "13": 35.0}
        linhas = {l["dezenas"]: l for l in body["linhas"]}
        assert set(linhas) == {15, 16, 17, 18, 19, 20}

        # aposta simples
        simples = linhas[15]
        assert simples["combos_simples"] == 1 and simples["custo_estimado"] == 3.50
        assert simples["faixas"]["15 acertos"]["one_in"] == 3_268_760
        assert simples["qualquer"]["one_in"] == 9.44  # ganhar alguma faixa

        # 20 dezenas: C(20,15) = 15.504 apostas -> R$ 54.264,00
        assert linhas[20]["combos_simples"] == 15_504
        assert linhas[20]["custo_estimado"] == 54_264.00

        # O retorno das faixas FIXAS é constante: uma aposta de k dezenas é
        # exatamente C(k,15) apostas simples, então a fração não muda.
        pcts = {l["retorno_fixo"]["pct"] for l in body["linhas"]}
        assert len(pcts) == 1, f"retorno fixo deveria ser constante, veio {pcts}"
        assert abs(pcts.pop() - 25.67) < 0.01

        # A Mega não tem prêmio fixo — tudo é rateio.
        mega = c.get("/api/odds/table?loteria=mega").json()
        assert mega["premios_fixos"] == {}
        assert all(l["retorno_fixo"]["valor"] == 0 for l in mega["linhas"])


def test_aleatoriedade_lotofacil():
    with make_client() as c:
        # 60 sorteios sintéticos só para o endpoint responder
        db.upsert_draws(
            [{"concurso": 992000 + i, "data": "2026-01-01",
              "dezenas": sorted(((n * 7 + i) % 25) + 1 for n in range(15))}
             for i in range(60)],
            "lofa",
        )
        r = c.get("/api/stats/aleatoriedade?loteria=lofa")
        assert r.status_code == 200, r.text
        body = r.json()
        cs = body["chi_square"]
        # 25 dezenas -> 24 graus de liberdade; crítico de 5% ≈ 36,4 (tabela)
        assert cs["graus_liberdade"] == 24
        assert abs(cs["critico_5pct"] - 36.4) < 0.1
        assert cs["nivel"] in ("ok", "limite", "atipico")
        assert 0.0 <= cs["p_valor"] <= 1.0
        assert len(cs["freq"]) == 25

        # indicadores trazem observado e teórico
        chaves = {i["chave"] for i in body["indicadores"]}
        assert {"pares", "moldura", "miolo", "repetidas_anterior"}.issubset(chaves)
        # média teórica de "repetidas" na Lotofácil: 15*15/25 = 9
        rep = next(i for i in body["indicadores"] if i["chave"] == "repetidas_anterior")
        assert rep["media_teorica"] == 9.0
        # soma teórica: 15 * (1+25)/2 = 195
        assert body["soma"]["media_teorica"] == 195.0


def test_chi2_critico_bate_com_a_tabela():
    """A aproximação de Wilson–Hilferty precisa bater com a tabela publicada."""
    from app import stats

    assert abs(stats._chi2_critico(24) - 36.415) < 0.05   # Lotofácil (25 dezenas)
    assert abs(stats._chi2_critico(59) - 77.931) < 0.05   # Mega (60 dezenas)
    assert abs(stats._chi2_critico(9) - 16.919) < 0.05


def test_chi2_p_valor_conhecido():
    """p-valor conferido contra valores de referência do qui-quadrado."""
    from app import stats

    # chi2 igual aos graus de liberdade -> p perto de 0,45 para gl=24
    assert abs(stats._gamma_q(24 / 2, 24 / 2) - 0.4562) < 0.01
    # mediana: chi2 = 23,337 com gl=24 -> p = 0,50
    assert abs(stats._gamma_q(24 / 2, 23.337 / 2) - 0.50) < 0.01
    # cauda: chi2 = 36,415 com gl=24 -> p = 0,05
    assert abs(stats._gamma_q(24 / 2, 36.415 / 2) - 0.05) < 0.005


def test_config_endpoint():
    with make_client() as c:
        cfg = c.get("/api/config?loteria=lofa").json()
        assert cfg["code"] == "lofa" and cfg["cols"] == 5
        assert cfg["escolher"] == 15 and cfg["max_escolher"] == 20
        assert cfg["garantias"] == [11, 12, 13, 14]
        mega = c.get("/api/config?loteria=mega").json()
        assert mega["cols"] == 10 and mega["garantias"] == [4, 5]


def test_proximo_nao_fica_defasado():
    with make_client() as c:
        cc = 998500
        db.upsert_draws([{"concurso": cc, "data": "2026-05-01", "dezenas": LOFA_15}], "lofa")
        # meta "próximo" defasada (anterior ao último já no cache)
        db.set_meta("proximo:lofa", {"concurso": cc - 100, "data": "2026-01-01", "estimativa": 1, "acumulado": True})
        st = c.get("/api/status?loteria=lofa").json()
        # status deve derivar do último local (+1), não repetir o valor defasado
        assert st["proximo"]["concurso"] == cc + 1
        assert st["proximo"]["data"] is None


def test_reenviar_ultimo_atualiza_proximo():
    with make_client() as c:
        cc = 999100
        db.upsert_draws([{"concurso": cc, "data": "2026-06-01", "dezenas": LOFA_15}], "lofa")
        db.set_meta("proximo:lofa", {"concurso": cc - 200, "data": "2026-01-01", "estimativa": 1, "acumulado": True})
        # reenvia o payload do último (já no cache): deve atualizar o "próximo"
        payload = {
            "numero": cc,
            "listaDezenas": [f"{n:02d}" for n in LOFA_15],
            "dataApuracao": "01/06/2026",
            "numeroConcursoProximo": cc + 1,
            "dataProximoConcurso": "03/06/2026",
            "valorEstimadoProximoConcurso": 5000000,
        }
        c.post("/api/import-payloads?loteria=lofa", json={"payloads": [payload]})
        st = c.get("/api/status?loteria=lofa").json()
        assert st["proximo"]["concurso"] == cc + 1
        assert st["proximo"]["data"] == "2026-06-03"


def test_validacao_dezenas_por_loteria():
    with make_client() as c:
        sid = _login(c)
        h = {"X-Session-Id": sid}
        # Lotofácil com número fora do volante (26)
        r = c.post("/api/bets", json={"loteria": "lofa", "concurso": 1, "origem": "manual", "dezenas": list(range(1, 15)) + [26]}, headers=h)
        assert r.status_code == 422
        # Lotofácil com menos de 15 dezenas
        r = c.post("/api/bets", json={"loteria": "lofa", "concurso": 1, "origem": "manual", "dezenas": [1, 2, 3]}, headers=h)
        assert r.status_code == 422
        # Mega com 61 (fora do intervalo)
        r = c.post("/api/bets", json={"loteria": "mega", "concurso": 1, "origem": "manual", "dezenas": [1, 2, 3, 4, 5, 61]}, headers=h)
        assert r.status_code == 422
