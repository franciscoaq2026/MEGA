import random

from app import generator

DRAWS = [
    {"concurso": i, "data": f"2024-01-{i:02d}", "dezenas": sorted(random.Random(i).sample(range(1, 61), 6))}
    for i in range(1, 51)
]


def _check_valid(jogo, k):
    assert len(jogo) == k
    assert len(set(jogo)) == k
    assert all(1 <= n <= 60 for n in jogo)
    assert jogo == sorted(jogo)


def test_todas_estrategias_geram_jogos_validos():
    rng = random.Random(1)
    for estrategia in generator.GERADORES:
        for k in (6, 10, 20):
            jogos = generator.gerar(DRAWS, estrategia, jogos=3, dezenas=k, rng=rng)
            assert len(jogos) == 3
            for j in jogos:
                _check_valid(j["dezenas"], k)
                assert j["soma"] == sum(j["dezenas"])


def test_aleatorio_funciona_sem_historico():
    jogos = generator.gerar([], "aleatorio", jogos=2, dezenas=6, rng=random.Random(2))
    assert len(jogos) == 2


def test_balanceado_respeita_restricoes():
    rng = random.Random(3)
    for _ in range(20):
        jogo = generator.balanceado(rng, DRAWS, 6)
        soma = sum(jogo)
        pares = sum(1 for n in jogo if n % 2 == 0)
        assert 141 <= soma <= 225  # 183 ± 42
        assert 2 <= pares <= 4


def test_padrao_popular():
    assert generator.padrao_popular([1, 5, 9, 13, 17, 21])  # PA e todas ≤ 31
    assert generator.padrao_popular([10, 20, 30, 40, 50, 60])  # mesma coluna
    assert generator.padrao_popular([1, 2, 3, 4, 33, 58])  # 4 consecutivos
    assert not generator.padrao_popular([2, 14, 27, 38, 45, 59])
    senas = {(4, 5, 30, 33, 41, 52)}
    assert generator.padrao_popular([4, 5, 30, 33, 41, 52], senas)


def test_anti_rateio_evita_padroes():
    rng = random.Random(4)
    jogos = generator.gerar(DRAWS, "aleatorio", jogos=10, dezenas=6, anti_rateio=True, rng=rng)
    for j in jogos:
        assert j["padroes_populares"] == []


def test_odds_valores_conhecidos():
    o6 = generator.odds(6)
    assert o6["combos_simples"] == 1
    assert o6["faixas"]["sena"]["one_in"] == 50063860
    assert o6["faixas"]["quina"]["one_in"] == 154518
    assert o6["faixas"]["quadra"]["one_in"] == 2332

    o15 = generator.odds(15)
    assert o15["combos_simples"] == 5005
    assert o15["faixas"]["sena"]["one_in"] == round(1 / (5005 / 50063860))

    # 20 dezenas (máximo atual da Caixa): caso do bolão da Aldeota no 3010
    o20 = generator.odds(20)
    assert o20["combos_simples"] == 38760
    assert o20["faixas"]["sena"]["one_in"] == 1292


def test_distribuicao_acertos_lotofacil():
    """A régua que julga um resultado já saído. Valores fechados da
    hipergeométrica 15 de 25 (esperado = 15·15/25 = 9)."""
    d = generator.distribuicao_acertos(15, "lofa")
    assert d["esperado"] == 9.0
    assert d["mais_provavel"] == 9
    assert abs(sum(l["prob"] for l in d["linhas"]) - 1) < 1e-12
    por_acerto = {l["acertos"]: l for l in d["linhas"]}
    # 15 acertos = 1 em 3.268.760, a chance da faixa principal
    assert round(1 / por_acerto[15]["prob"]) == 3268760
    # premiar (>= 11) sai em ~10,6% dos jogos — 1 em 9
    assert d["premiado"]["one_in"] == 9
    assert round(d["premiado"]["pct"], 2) == 10.59
    # caudas estritas somam 1 com a própria linha
    l9 = por_acerto[9]
    assert abs(l9["p_menos"] + l9["prob"] + l9["p_mais"] - 1) < 1e-12
    # abaixo de 5 acertos é impossível: sobram só 10 dezenas fora do sorteio
    assert min(por_acerto) == 5


def test_distribuicao_acertos_mega_e_aposta_maior():
    d6 = generator.distribuicao_acertos(6)
    assert d6["esperado"] == 0.6
    assert d6["mais_provavel"] == 0  # o resultado mais comum é não acertar nada
    assert abs(sum(l["prob"] for l in d6["linhas"]) - 1) < 1e-12
    # cada dezena a mais no bilhete sobe o esperado em sorteadas/total
    d20 = generator.distribuicao_acertos(20)
    assert d20["esperado"] == 2.0
    d18 = generator.distribuicao_acertos(18, "lofa")
    assert d18["esperado"] == 10.8
    assert d18["mais_provavel"] == 11


def test_avaliar_acertos_veredito():
    """Régua de 1 desvio-padrão: na Lotofácil simples (9 ± 1,22), 8 a 10 é o
    normal; 11 para cima é acima do esperado; 7 para baixo, abaixo."""
    niveis = {h: generator.avaliar_acertos(h, 15, "lofa")["nivel"] for h in range(5, 16)}
    assert [niveis[h] for h in (5, 6, 7)] == ["abaixo"] * 3
    assert [niveis[h] for h in (8, 9, 10)] == ["tipico"] * 3
    assert [niveis[h] for h in (11, 12, 13, 14, 15)] == ["acima"] * 5

    a9 = generator.avaliar_acertos(9, 15, "lofa")
    assert a9["diferenca"] == 0.0
    assert a9["faixa_tipica"] == [7.8, 10.2]
    # ~34% dos jogos fariam pior e ~34% melhor: 9 acertos é o meio da curva
    assert round(a9["pct_pior"]) == 34
    assert round(a9["pct_melhor"]) == 34
