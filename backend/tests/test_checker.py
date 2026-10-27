import random
import zlib
from math import comb

import pytest

from app import checker, generator, lotteries

DRAWS = [
    {"concurso": i, "data": f"2024-01-{i:02d}", "dezenas": sorted(random.Random(i).sample(range(1, 61), 6))}
    for i in range(1, 201)
]


def test_conferir_faixas():
    resultado = [1, 2, 3, 4, 5, 6]
    c = checker.conferir([1, 2, 3, 4, 5, 6], resultado)
    assert (c["acertos"], c["faixa"]) == (6, "sena")
    assert checker.conferir([1, 2, 3, 4, 5, 60], resultado)["faixa"] == "quina"
    assert checker.conferir([1, 2, 3, 4, 50, 60], resultado)["faixa"] == "quadra"
    assert checker.conferir([1, 2, 3, 40, 50, 60], resultado)["faixa"] is None
    # aposta de 10 dezenas cobrindo todas as 6
    aposta10 = [1, 2, 3, 4, 5, 6, 10, 20, 30, 40]
    c10 = checker.conferir(aposta10, resultado)
    assert (c10["acertos"], c10["faixa"]) == (6, "sena")


def test_conferir_traz_avaliacao_do_acaso():
    """A conferência situa o resultado na distribuição do acaso — a régua que
    diz se os acertos foram normais. Ver generator.avaliar_acertos."""
    resultado = list(range(1, 16))
    # 9 acertos de 15 dezenas na Lotofácil é EXATAMENTE a média (15·15/25)
    jogo = list(range(1, 10)) + list(range(16, 22))
    av = checker.conferir(jogo, resultado, "lofa")["avaliacao"]
    assert av["acertos"] == 9
    assert av["esperado"] == 9.0
    assert av["nivel"] == "tipico"
    # a avaliação usa o TAMANHO da aposta: 6 acertos numa aposta simples da
    # Mega é o extremo oposto — muito acima do esperado (0,6)
    av_mega = checker.conferir([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6])["avaliacao"]
    assert av_mega["esperado"] == 0.6
    assert av_mega["nivel"] == "acima"


def test_backtest_reprodutivel_e_proximo_do_acaso():
    r1 = checker.backtest(DRAWS, ultimos=100)
    r2 = checker.backtest(DRAWS, ultimos=100)
    assert r1 == r2  # rng semeado por concurso -> reprodutível
    assert r1["concursos_simulados"] == 100
    assert set(r1["estrategias"]) == {"aleatorio", "frequencia", "atrasados", "balanceado"}
    for nome, res in r1["estrategias"].items():
        assert 0.2 <= res["media_acertos"] <= 1.2, f"{nome} fora da faixa plausível"
        assert sum(res["distrib"].values()) == 100


def test_backtest_historico_insuficiente():
    with pytest.raises(ValueError):
        checker.backtest(DRAWS[:20], ultimos=100)


def test_backtest_semente_nao_depende_do_hash_do_processo():
    """A semente precisa ser estável entre processos.

    Antes ela usava `hash(nome)`, que o Python aleatoriza por processo
    (PYTHONHASHSEED): o mesmo backtest devolvia números diferentes a cada
    reinício do servidor, apesar do docstring prometer reprodutibilidade."""
    assert checker._semente(1000, "aleatorio") == checker._semente(1000, "aleatorio")
    assert checker._semente(1000, "aleatorio") != checker._semente(1000, "balanceado")
    # valor fixo: se a fórmula mudar, o backtest publicado muda junto
    assert checker._semente(2500, "aleatorio") == 2500 * 1000 + zlib.crc32(b"aleatorio") % 1000


DRAWS_LOFA = [
    {"concurso": i, "data": f"2024-01-{i:02d}", "dezenas": sorted(random.Random(i).sample(range(1, 26), 15))}
    for i in range(1, 201)
]


def _backtest_de_um_jogo_como_antes(draws, ultimos, loteria):
    """O backtest como era antes do parâmetro `jogos`: a estratégia sorteia o
    jogo direto, sem passar pelo gerador."""
    cfg = lotteries.get_loteria(loteria)
    pool = lotteries.numbers(cfg)
    inicio = max(50, len(draws) - ultimos)
    out = {}
    for nome, fn in generator.GERADORES.items():
        distrib = {i: 0 for i in range(cfg["escolher"] + 1)}
        for i in range(inicio, len(draws)):
            jogo = fn(random.Random(checker._semente(draws[i]["concurso"], nome)), draws[:i], cfg["escolher"], pool)
            distrib[len(set(jogo) & set(draws[i]["dezenas"]))] += 1
        out[nome] = distrib
    return out


def test_backtest_de_um_jogo_igual_ao_de_antes():
    """Com 1 jogo por concurso, o backtest que passa pelo gerador dá os mesmos
    jogos que o antigo: os números publicados não mudam."""
    for loteria, draws in (("mega", DRAWS), ("lofa", DRAWS_LOFA)):
        r = checker.backtest(draws, ultimos=60, loteria=loteria)
        antes = _backtest_de_um_jogo_como_antes(draws, 60, loteria)
        assert {n: e["distrib"] for n, e in r["estrategias"].items()} == antes


def test_backtest_com_varios_jogos_por_concurso():
    r = checker.backtest(DRAWS_LOFA, ultimos=60, loteria="lofa", jogos=3)
    n = r["concursos_simulados"]
    assert (n, r["jogos_por_concurso"], r["espalhar"], r["faixa_minima"]) == (60, 3, True, 11)
    assert r["gasto"] == 60 * 3 * 3.5
    for e in r["estrategias"].values():
        assert sum(e["distrib"].values()) == n * 3
        assert set(e["premios"]) == {11, 12, 13, 14, 15}
        # concurso premiado = pelo menos um jogo premiado naquele concurso
        assert e["concursos_com_premio"] <= min(n, sum(e["premios"].values()))
        assert e["retorno_fixo"] == 7 * e["premios"][11] + 14 * e["premios"][12] + 35 * e["premios"][13]
        assert e["premios_rateio"] == e["premios"][14] + e["premios"][15]
    acaso = r["acaso"]
    assert acaso["min"] <= acaso["esperado"] <= acaso["max"]
    assert acaso["media_min"] < 9.0 < acaso["media_max"]
    # com 1 jogo não há o que espalhar
    assert checker.backtest(DRAWS_LOFA, ultimos=20, loteria="lofa", jogos=1)["espalhar"] is False
    # na Mega todas as faixas são de rateio: não há retorno fixo a somar
    mega = checker.backtest(DRAWS, ultimos=60, jogos=2)
    assert all(e["retorno_fixo"] is None for e in mega["estrategias"].values())


def test_resumir_reaproveita_janela_e_lote():
    """Os jogos de um concurso não dependem da janela, e os primeiros jogos de
    um lote maior são o lote menor: uma simulação de 80 concursos x 4 jogos
    responde por qualquer janela e lote menores, igual a simular de novo."""
    sim = checker.simular(DRAWS_LOFA, ultimos=80, loteria="lofa", jogos=4)
    for ultimos, jogos in ((80, 4), (60, 3), (30, 1)):
        assert checker.resumir(sim, ultimos, jogos) == checker.backtest(
            DRAWS_LOFA, ultimos=ultimos, loteria="lofa", jogos=jogos
        )
    with pytest.raises(ValueError):
        checker.resumir(sim, 80, 5)


def test_regua_do_acaso_estreita_com_a_janela():
    """A faixa da sorte, proporcionalmente, encolhe com mais concursos: é o
    que a tela usa para dizer que 50 concursos são quase só sorte."""
    janelas = checker.backtest(DRAWS_LOFA, ultimos=60, loteria="lofa", jogos=3)["acaso"]["janelas"]
    assert [j["concursos"] for j in janelas] == [50, 100, 200]
    larguras = [(j["max"] - j["min"]) / j["concursos"] for j in janelas]
    assert larguras[0] > larguras[1] > larguras[2]
    margens = [j["media_max"] - j["media_min"] for j in janelas]
    assert margens[0] > margens[1] > margens[2]


def test_faixa_binomial_cobre_95_por_cento():
    for n, p in ((50, 0.3), (200, 0.47), (100, 0.002), (500, 0.47)):
        lo, hi = checker._faixa_binomial(n, p)
        dentro = sum(comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(lo, hi + 1))
        assert dentro >= 0.95, (n, p, lo, hi)
    assert checker._faixa_binomial(10, 0.0) == (0, 0)
