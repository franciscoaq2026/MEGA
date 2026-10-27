import random
from statistics import mean, pstdev

import pytest

from app import generator, stats

DRAWS = [
    {"concurso": 1, "data": "2024-01-01", "dezenas": [1, 2, 3, 4, 5, 6]},
    {"concurso": 2, "data": "2024-01-08", "dezenas": [1, 2, 3, 40, 50, 60]},
    {"concurso": 3, "data": "2024-01-15", "dezenas": [1, 10, 20, 30, 40, 59]},
]


def test_frequency_counts_and_window():
    r = stats.frequency(DRAWS)
    counts = {f["n"]: f["count"] for f in r["freq"]}
    assert counts[1] == 3
    assert counts[2] == 2
    assert counts[59] == 1
    assert counts[13] == 0
    assert r["hot"][0]["n"] == 1

    r2 = stats.frequency(DRAWS, window=1)  # só o concurso 3
    counts2 = {f["n"]: f["count"] for f in r2["freq"]}
    assert counts2[1] == 1 and counts2[2] == 0
    assert r2["draws_considered"] == 1


def test_current_delays():
    r = stats.current_delays(DRAWS)
    d = {x["n"]: x for x in r["delays"]}
    assert d[1]["delay"] == 0  # saiu no último
    assert d[5]["delay"] == 2 and d[5]["last_concurso"] == 1
    assert d[13]["delay"] == 3 and d[13]["last_concurso"] is None  # nunca saiu


def test_parity_theoretical_sums_to_100():
    r = stats.parity_distribution(DRAWS)
    assert abs(sum(row["theoretical_pct"] for row in r["rows"]) - 100) < 0.2
    # concurso 1 tem 3 pares (2,4,6); concursos 2 e 3 têm 4 pares cada
    by_evens = {row["evens"]: row["count"] for row in r["rows"]}
    assert by_evens[3] == 1
    assert by_evens[4] == 2


def test_sum_distribution():
    r = stats.sum_distribution(DRAWS)
    assert r["min"] == 21  # 1+2+3+4+5+6
    assert r["total_draws"] == 3
    assert sum(b["count"] for b in r["bins"]) == 3
    assert r["theoretical_mean"] == 183.0


def test_top_pairs():
    r = stats.top_pairs(DRAWS, limit=3)
    assert r["pairs"][0]["a"] == 1 and r["pairs"][0]["b"] == 2  # par (1,2) saiu 2x
    assert r["pairs"][0]["count"] == 2


def test_xray_uses_only_prior_history():
    r = stats.xray(DRAWS, 3)
    assert r["prior_draws"] == 2
    per_n = {x["n"]: x for x in r["dezenas"]}
    assert per_n[1]["freq_before"] == 2
    assert per_n[1]["freq_rank"] == 1
    assert per_n[10]["freq_before"] == 0
    assert per_n[40]["delay_before"] == 0  # saiu no concurso 2
    assert 0 <= r["hot6_matches"] <= 6
    with pytest.raises(ValueError):
        stats.xray(DRAWS, 99)
    with pytest.raises(ValueError):
        stats.xray(DRAWS, 1)


def _historico(total, sorteadas, n, seed, pesos=None):
    """Histórico sintético: sorteio honesto, ou com algumas dezenas mais
    pesadas quando `pesos` vem (peso por dezena)."""
    rng = random.Random(seed)
    numeros = list(range(1, total + 1))
    out = []
    for i in range(n):
        if pesos is None:
            dezenas = rng.sample(numeros, sorteadas)
        else:
            dezenas = generator._weighted_sample(rng, {x: pesos(x) for x in numeros}, sorteadas)
        out.append({"concurso": i + 1, "data": "2024-01-01", "dezenas": sorted(dezenas)})
    return out


def test_qui_quadrado_calibrado_para_sorteio_sem_repeticao():
    """Em históricos 100% aleatórios, a estatística fica, em média, nos graus de
    liberdade. Com a fórmula de Pearson (bola devolvida ao globo), a média da
    Lotofácil era 10 em vez de 24 e o teste nunca acusava desvio."""
    for loteria, total, sorteadas in (("lofa", 25, 15), ("mega", 60, 6)):
        valores = [
            stats.chi_square_frequencias(_historico(total, sorteadas, 200, seed), loteria)["chi2"]
            for seed in range(150)
        ]
        gl = total - 1
        assert abs(mean(valores) - gl) < 0.12 * gl, (loteria, mean(valores))


def test_sinais_de_sorteio_honesto_ficam_em_volta_de_zero():
    """Sorteio honesto: o z de cada sinal segue a normal padrão — média perto de
    0 e desvio perto de 1 entre muitos históricos."""
    zs = {"frequencia": [], "atrasados": []}
    for seed in range(60):
        r = stats.sinais_concurso_a_concurso(_historico(25, 15, 260, seed), "lofa")
        for nome, s in r["sinais"].items():
            zs[nome].append(s["z"])
    for nome, valores in zs.items():
        assert abs(mean(valores)) < 0.45, (nome, mean(valores))
        assert 0.6 < pstdev(valores) < 1.45, (nome, pstdev(valores))


def test_sinal_de_dezenas_mais_pesadas_e_recomendado():
    """Com cinco dezenas um pouco mais pesadas, as mais sorteadas continuam
    saindo mais: o teste pega, o jogo com elas acerta mais e o app recomenda a
    Frequência."""
    viciado = _historico(25, 15, 700, 1, pesos=lambda x: 1.6 if x <= 5 else 1.0)
    f = stats.sinais_concurso_a_concurso(viciado, "lofa")["sinais"]["frequencia"]
    assert f["z"] > 3 and f["nivel"] == "claro"
    assert f["acertos_jogo"] > f["esperado"]
    assert generator.recomendacao(viciado, 3, "lofa")["estrategia"] == "frequencia"


def test_historico_honesto_quase_sempre_recomenda_aleatorio():
    recomendadas = [
        generator.recomendacao(_historico(25, 15, 260, seed), 3, "lofa")["estrategia"]
        for seed in range(40)
    ]
    assert recomendadas.count("aleatorio") >= 34, recomendadas


def test_recomendacao_espalhar_custo_e_chance():
    """Só a estratégia depende do histórico; o resto são as contas fixas do
    painel de probabilidades."""
    hist = _historico(25, 15, 200, 3)
    r = generator.recomendacao(hist, 3, "lofa")
    assert (r["custo"], r["preco"], r["menor_premio"]) == (10.5, 3.5, 11)
    assert r["espalhar"]["faz_diferenca"] is True  # 30,9% espalhando x 28,5% soltos
    assert r["chance"] == generator.odds_carteira(3, "lofa", espalhar=True)["qualquer"]
    assert generator.recomendacao(hist, 1, "lofa")["espalhar"]["faz_diferenca"] is False
    mega = generator.recomendacao(_historico(60, 6, 200, 3), 3, "mega")
    assert mega["espalhar"]["faz_diferenca"] is False  # 6 de 60: os jogos já quase não se tocam
    assert mega["custo"] == 18.0
    with pytest.raises(ValueError):
        stats.sinais_concurso_a_concurso(hist[:120], "lofa")  # curto demais
