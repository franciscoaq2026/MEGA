import random
import zlib

import pytest

from app import checker

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


def test_backtest_historico_inteiro_e_regua_do_acaso():
    """ultimos=0 simula tudo a partir do mínimo de histórico, e o resultado traz
    a margem de 95% do acaso e o z de cada estratégia para poder ser lido."""
    r = checker.backtest(DRAWS, ultimos=0)
    assert r["concursos_simulados"] == len(DRAWS) - 50
    # Mega simples: dp de 1 jogo = sqrt(6·6·54·54 / (60²·59)) ≈ 0,7027
    dp_media = (6 * 6 * 54 * 54 / (60 * 60 * 59)) ** 0.5 / (len(DRAWS) - 50) ** 0.5
    assert abs(r["margem_95"] - 1.96 * dp_media) < 0.001
    for res in r["estrategias"].values():
        z = (res["media_acertos"] - r["esperado_por_jogo"]) / dp_media
        assert abs(res["z"] - z) < 0.02


def test_backtest_incremental_igual_a_recontar_o_passado():
    """O backtest mantém frequência/atraso incrementalmente; o jogo de cada
    concurso tem de ser o mesmo que as estratégias geram recontando o passado."""
    import random as _random

    from app import generator, lotteries

    pool = lotteries.numbers(lotteries.get_loteria("mega"))
    r = checker.backtest(DRAWS, ultimos=30)
    esperado = {nome: 0 for nome in generator.GERADORES}
    for i in range(len(DRAWS) - 30, len(DRAWS)):
        alvo = DRAWS[i]
        for nome, fn in generator.GERADORES.items():
            rng = _random.Random(checker._semente(alvo["concurso"], nome))
            jogo = fn(rng, DRAWS[:i], 6, pool)
            esperado[nome] += len(set(jogo) & set(alvo["dezenas"]))
    for nome, total in esperado.items():
        assert r["estrategias"][nome]["media_acertos"] == round(total / 30, 3)
