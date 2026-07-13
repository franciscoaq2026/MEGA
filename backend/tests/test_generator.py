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
