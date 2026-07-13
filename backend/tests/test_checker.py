import random

import pytest

from app import checker

DRAWS = [
    {"concurso": i, "data": f"2024-01-{i:02d}", "dezenas": sorted(random.Random(i).sample(range(1, 61), 6))}
    for i in range(1, 201)
]


def test_conferir_faixas():
    resultado = [1, 2, 3, 4, 5, 6]
    assert checker.conferir([1, 2, 3, 4, 5, 6], resultado) == {"acertos": 6, "faixa": "sena"}
    assert checker.conferir([1, 2, 3, 4, 5, 60], resultado)["faixa"] == "quina"
    assert checker.conferir([1, 2, 3, 4, 50, 60], resultado)["faixa"] == "quadra"
    assert checker.conferir([1, 2, 3, 40, 50, 60], resultado)["faixa"] is None
    # aposta de 10 dezenas cobrindo todas as 6
    aposta10 = [1, 2, 3, 4, 5, 6, 10, 20, 30, 40]
    assert checker.conferir(aposta10, resultado) == {"acertos": 6, "faixa": "sena"}


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
