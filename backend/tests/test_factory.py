import random

import pytest

from app import analysis, generator, lotteries

DRAWS = [
    {"concurso": i, "data": "", "dezenas": sorted(random.Random(i).sample(range(1, 61), 6))}
    for i in range(1, 301)
]


def test_metrics_basico():
    m = analysis.metrics([1, 2, 3, 4, 5, 6], anterior=[4, 5, 6, 7, 8, 9])
    assert m["soma"] == 21
    assert m["pares"] == 3 and m["impares"] == 3
    assert m["primos"] == 3  # 2, 3, 5 (1 não é primo)
    assert m["consecutivos"] == 6
    assert m["baixas"] == 6 and m["altas"] == 0
    assert m["repetidas_anterior"] == 3  # 4,5,6


def test_moldura_definicao():
    # Mega: volante 6x10 — 1 e 10 (cantos de cima), 51 e 60 (cantos de baixo)
    mega = analysis.moldura_set(lotteries.get_loteria("mega"))
    assert 1 in mega and 10 in mega
    assert 60 in mega and 51 in mega
    assert 22 not in mega and 35 not in mega
    # 2 linhas cheias (20) + 2 colunas nas 4 linhas do meio (8) = 28
    assert len(mega) == 28


def test_moldura_lotofacil():
    # Lotofácil: volante 5x5 — a borda são 16 dezenas, o miolo 9 (7,8,9,12,13,14,17,18,19)
    lofa = analysis.moldura_set(lotteries.get_loteria("lofa"))
    assert len(lofa) == 16
    assert {1, 5, 21, 25}.issubset(lofa)  # os quatro cantos
    assert lofa.isdisjoint({7, 8, 9, 12, 13, 14, 17, 18, 19})  # miolo


def test_historical_ranges_e_score():
    rg = analysis.historical_ranges(DRAWS)
    assert rg["draws_considered"] == 300
    assert "soma" in rg["ranges"]
    assert rg["ranges"]["soma"]["p10"] < rg["ranges"]["soma"]["p90"]
    sc = analysis.score([2, 14, 27, 38, 45, 59], rg)
    assert 0 <= sc["nota"] <= 100
    assert sc["criterios"]


def test_gerar_avancado_respeita_filtros():
    filtros = {"pares": [3, 3], "soma": [150, 210], "consecutivos_max": 2}
    r = generator.gerar_avancado(
        DRAWS, jogos=5, dezenas=6, filtros=filtros, rng=random.Random(1)
    )
    assert r["gerados"] == 5
    for j in r["jogos"]:
        assert j["metrics"]["pares"] == 3
        assert 150 <= j["metrics"]["soma"] <= 210
        assert j["metrics"]["consecutivos"] <= 2


def test_gerar_avancado_incluir_excluir():
    r = generator.gerar_avancado(
        DRAWS, jogos=3, dezenas=6, incluir=[7, 13], excluir=[1, 2, 3], rng=random.Random(2)
    )
    for j in r["jogos"]:
        assert 7 in j["dezenas"] and 13 in j["dezenas"]
        assert not ({1, 2, 3} & set(j["dezenas"]))


def test_roda_completa():
    r = generator.roda_completa([1, 2, 3, 4, 5, 6, 7])
    assert r["num_jogos"] == 7  # C(7,6)
    assert len(r["jogos"]) == 7
    assert any(g["garante"] == "sena" for g in r["garantias"])


def test_fechamento_reduzido_garante_e_verifica():
    r = generator.fechamento_reduzido(list(range(1, 11)), garantia=4)
    assert r["garantia_verificada"] is True
    assert r["num_jogos"] < r["num_jogos_roda_completa"]
    # verificação independente: todo 6-subset das 10 dezenas tem ganho >= quadra
    from itertools import combinations

    jogos = [set(j) for j in r["jogos"]]
    for alvo in combinations(range(1, 11), 6):
        assert any(len(j & set(alvo)) >= 4 for j in jogos)
