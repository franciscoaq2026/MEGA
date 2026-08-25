"""Cálculos estatísticos sobre o histórico de sorteios.

Todas as funções recebem a lista de sorteios em ordem crescente de concurso
(como retornado por db.get_all_draws_asc) e são puras, para facilitar testes.

Nota honesta: nada aqui tem poder preditivo — cada sorteio é independente.
São ferramentas de exploração de dados.
"""

from collections import Counter
from itertools import combinations
from math import comb
from statistics import pstdev

from . import lotteries

# Pool padrão (Mega) para quem chama sem passar `numbers`. Toda função aqui
# aceita o pool da loteria; os routers sempre passam o correto.
NUMBERS = range(1, 61)


def _window(draws: list[dict], window: int) -> list[dict]:
    return draws[-window:] if window and window > 0 else draws


def _pool(numbers=None):
    return numbers if numbers is not None else NUMBERS


def frequency(draws: list[dict], window: int = 0, numbers=None, pick: int = 6) -> dict:
    nums = _pool(numbers)
    considered = _window(draws, window)
    counts = Counter()
    for d in considered:
        counts.update(d["dezenas"])
    freq = [{"n": n, "count": counts.get(n, 0)} for n in nums]
    ordered = sorted(freq, key=lambda f: (-f["count"], f["n"]))
    expected = len(considered) * pick / len(list(nums))  # média esperada por número
    return {
        "window": window,
        "draws_considered": len(considered),
        "expected_per_number": round(expected, 2),
        "freq": freq,
        "hot": ordered[:10],
        "cold": list(reversed(ordered[-10:])),
    }


def current_delays(draws: list[dict], numbers=None) -> dict:
    """Atraso atual: há quantos concursos cada número não sai
    (0 = saiu no último sorteio; nunca saiu = total de sorteios)."""
    nums = _pool(numbers)
    total = len(draws)
    last_index: dict[int, int] = {}
    for i, d in enumerate(draws):
        for n in d["dezenas"]:
            last_index[n] = i
    delays = []
    for n in nums:
        if n in last_index:
            delays.append(
                {
                    "n": n,
                    "delay": total - 1 - last_index[n],
                    "last_concurso": draws[last_index[n]]["concurso"],
                }
            )
        else:
            delays.append({"n": n, "delay": total, "last_concurso": None})
    top = sorted(delays, key=lambda x: (-x["delay"], x["n"]))[:10]
    return {"total_draws": total, "delays": delays, "top": top}


def parity_distribution(draws: list[dict], numbers=None, drawn: int = 6) -> dict:
    """Distribuição de quantidade de números pares por sorteio, comparada com
    a probabilidade teórica (hipergeométrica) do pool da loteria."""
    nums = list(_pool(numbers))
    pares_pool = sum(1 for n in nums if n % 2 == 0)
    impares_pool = len(nums) - pares_pool
    total_combos = comb(len(nums), drawn)
    observed = Counter(sum(1 for n in d["dezenas"] if n % 2 == 0) for d in draws)
    total = len(draws)
    rows = []
    for evens in range(drawn + 1):
        theoretical = (
            comb(pares_pool, evens) * comb(impares_pool, drawn - evens) / total_combos
        )
        count = observed.get(evens, 0)
        rows.append(
            {
                "evens": evens,
                "odds": drawn - evens,
                "count": count,
                "observed_pct": round(100 * count / total, 2) if total else 0,
                "theoretical_pct": round(100 * theoretical, 2),
            }
        )
    return {"total_draws": total, "rows": rows}


def sum_distribution(draws: list[dict], bin_size: int = 15, numbers=None, drawn: int = 6) -> dict:
    nums = list(_pool(numbers))
    lo, hi = nums[0], nums[-1]
    # soma mínima = as `drawn` menores; máxima = as `drawn` maiores dezenas
    soma_min = sum(nums[:drawn])
    soma_max = sum(nums[-drawn:])
    theoretical_mean = round(drawn * (lo + hi) / 2, 1)
    sums = [sum(d["dezenas"]) for d in draws]
    bins: list[dict] = []
    start = soma_min
    while start <= soma_max:
        end = min(start + bin_size - 1, soma_max)
        bins.append({"from": start, "to": end, "label": f"{start}–{end}", "count": 0})
        start = end + 1
    for s in sums:
        idx = min((s - soma_min) // bin_size, len(bins) - 1)
        idx = max(0, idx)
        bins[idx]["count"] += 1
    return {
        "total_draws": len(sums),
        "bins": bins,
        "mean": round(sum(sums) / len(sums), 1) if sums else None,
        "min": min(sums) if sums else None,
        "max": max(sums) if sums else None,
        "theoretical_mean": theoretical_mean,
    }


def top_pairs(draws: list[dict], limit: int = 15, numbers=None, drawn: int = 6) -> dict:
    nums = list(_pool(numbers))
    counts: Counter = Counter()
    for d in draws:
        counts.update(combinations(sorted(d["dezenas"]), 2))
    pairs = [
        {"a": a, "b": b, "count": c}
        for (a, b), c in counts.most_common(limit)
    ]
    # média esperada de aparições de um par específico
    expected = len(draws) * comb(drawn, 2) / comb(len(nums), 2)
    return {"total_draws": len(draws), "pairs": pairs, "expected_per_pair": round(expected, 2)}


# ---- Teste de aleatoriedade: os sorteios se comportam como acaso puro? ----


def _gamma_q(a: float, x: float) -> float:
    """Função gama incompleta regularizada Q(a,x) = 1 - P(a,x).

    Implementação clássica (série para x < a+1, fração continuada acima),
    para não depender do scipy. Usada só para o p-valor do qui-quadrado."""
    import math

    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1.0:  # série
        ap, soma, termo = a, 1.0 / a, 1.0 / a
        for _ in range(500):
            ap += 1
            termo *= x / ap
            soma += termo
            if abs(termo) < abs(soma) * 1e-14:
                break
        return 1.0 - soma * math.exp(-x + a * math.log(x) - gln)
    # fração continuada (Lentz)
    tiny = 1e-300
    b, c, dd = x + 1.0 - a, 1.0 / tiny, 1.0 / (x + 1.0 - a)
    h = dd
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        dd = an * dd + b
        if abs(dd) < tiny:
            dd = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        dd = 1.0 / dd
        delta = dd * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def _chi2_critico(gl: int, alpha: float = 0.05) -> float:
    """Valor crítico do qui-quadrado por Wilson–Hilferty (bate com a tabela
    até a 2ª casa: gl=24 -> 36,4; gl=59 -> 77,9)."""
    from math import sqrt

    z = 1.6448536269514722  # z de 95%
    return gl * (1 - 2 / (9 * gl) + z * sqrt(2 / (9 * gl))) ** 3


def chi_square_frequencias(draws: list[dict], loteria: str = "mega") -> dict:
    """Testa se as dezenas saem com a mesma frequência (hipótese de acaso).

    Sob acaso puro, o valor esperado da própria estatística é igual aos graus
    de liberdade. Um qui-quadrado próximo de `gl` é a assinatura de um sorteio
    honesto — e é o que derruba a ideia de "dezena quente"."""
    cfg = lotteries.get_loteria(loteria)
    pool = lotteries.numbers(cfg)
    n = len(draws)
    if n < 30:
        raise ValueError("histórico curto demais para o teste (mínimo 30 concursos)")

    counts = Counter()
    for d in draws:
        counts.update(d["dezenas"])
    esperado = n * cfg["sorteadas"] / cfg["total"]
    chi2 = sum((counts.get(x, 0) - esperado) ** 2 / esperado for x in pool)
    gl = cfg["total"] - 1
    critico = _chi2_critico(gl)
    p = _gamma_q(gl / 2, chi2 / 2)

    freq = [
        {
            "n": x,
            "count": counts.get(x, 0),
            "pct": round(100 * counts.get(x, 0) / n, 2),
            "desvio": round(counts.get(x, 0) - esperado, 1),
        }
        for x in pool
    ]
    ordenado = sorted(freq, key=lambda f: -f["count"])

    # Veredito com três níveis. Um teste a 5% "reprova" 1 de cada 20 históricos
    # perfeitamente honestos — por isso um p entre 0,01 e 0,05 não é evidência
    # de viés, e o texto precisa dizer isso em vez de gritar "não é aleatório".
    def num(v, casas=1) -> str:
        """Número no padrão pt-BR (vírgula decimal) para o texto da interface."""
        return f"{v:.{casas}f}".replace(".", ",")

    if p >= 0.05:
        nivel, veredito = "ok", "compatível com o acaso"
        explica = (
            f"O desvio observado aparece em {round(100 * p)}% dos históricos "
            "perfeitamente aleatórios. Nada aqui indica que alguma dezena seja "
            "mais provável que outra."
        )
    elif p >= 0.01:
        nivel, veredito = "limite", "no limite, mas ainda dentro do esperado"
        explica = (
            f"Um desvio deste tamanho ou maior acontece em {num(100 * p)}% "
            "dos históricos honestos — ou seja, cerca de 1 em cada "
            f"{round(1 / p)}. Testar a 5% reprova 1 em cada 20 loterias "
            "íntegras, então isto é flutuação normal, não sinal de viés nem "
            "de dezena “viciada”."
        )
    else:
        nivel, veredito = "atipico", "desvio grande para o acaso puro"
        explica = (
            f"Um desvio deste tamanho aparece em menos de {num(max(100 * p, 0.01), 2)}% "
            "dos históricos aleatórios. Mesmo assim não é prova de viés: com "
            "sorteios físicos, pequenas diferenças entre as bolas e o próprio "
            "número de testes feitos explicam desvios assim. E, sobretudo, isso "
            "não torna nenhuma dezena mais provável no PRÓXIMO sorteio."
        )

    return {
        "draws_considered": n,
        "esperado_por_dezena": round(esperado, 1),
        "esperado_pct": round(100 * cfg["sorteadas"] / cfg["total"], 1),
        "chi2": round(chi2, 2),
        "graus_liberdade": gl,
        "chi2_esperado": gl,  # sob acaso puro, E[chi2] = gl
        "critico_5pct": round(critico, 1),
        "p_valor": round(p, 4),
        "nivel": nivel,
        "veredito": veredito,
        "explicacao": explica,
        "maior_desvio_pct": round(
            100 * max(abs(f["desvio"]) for f in freq) / esperado, 1
        ),
        "freq": freq,
        "mais_frequentes": ordenado[:5],
        "menos_frequentes": list(reversed(ordenado[-5:])),
    }


def _subconjuntos(cfg: dict) -> dict[str, set[int]]:
    """Indicadores que são 'quantas das sorteadas caem neste subconjunto'.
    Todos seguem a mesma hipergeométrica, então a teoria sai de graça."""
    from . import analysis

    pool = lotteries.numbers(cfg)
    moldura = analysis.moldura_set(cfg)
    corte = analysis.corte_baixas(cfg)
    return {
        "pares": {x for x in pool if x % 2 == 0},
        "primos": {x for x in pool if x in analysis.PRIMES},
        "moldura": moldura,
        "miolo": set(pool) - moldura,
        "baixas": {x for x in pool if x <= corte},
        "multiplos_3": {x for x in pool if x % 3 == 0},
    }


def indicadores_vs_teoria(draws: list[dict], loteria: str = "mega") -> dict:
    """Distribuição observada de cada indicador contra a teórica.

    Se os sorteios são aleatórios, as duas curvas coincidem — e é exatamente
    isso que se vê. É a resposta visual para "existe padrão na Lotofácil?"."""
    from . import analysis

    cfg = lotteries.get_loteria(loteria)
    total, sorteadas = cfg["total"], cfg["sorteadas"]
    n = len(draws)
    if not n:
        raise ValueError("cache vazio")

    def teorico(tam_subconjunto: int, x: int) -> float:
        if x > tam_subconjunto or sorteadas - x > total - tam_subconjunto:
            return 0.0
        return (
            comb(tam_subconjunto, x)
            * comb(total - tam_subconjunto, sorteadas - x)
            / comb(total, sorteadas)
        )

    saida = []
    for chave, conjunto in _subconjuntos(cfg).items():
        obs = Counter(len(set(d["dezenas"]) & conjunto) for d in draws)
        linhas = [
            {
                "valor": x,
                "observado_pct": round(100 * obs.get(x, 0) / n, 2),
                "teorico_pct": round(100 * teorico(len(conjunto), x), 2),
            }
            for x in range(sorteadas + 1)
            if obs.get(x, 0) or teorico(len(conjunto), x) > 0.001
        ]
        media_obs = sum(x * c for x, c in obs.items()) / n
        saida.append(
            {
                "chave": chave,
                "label": analysis.label(chave, loteria),
                "tamanho_conjunto": len(conjunto),
                "media_observada": round(media_obs, 2),
                "media_teorica": round(sorteadas * len(conjunto) / total, 2),
                "linhas": linhas,
            }
        )

    # Repetidas do concurso anterior: mesma hipergeométrica, com o subconjunto
    # sendo as próprias dezenas do sorteio anterior.
    if n > 1:
        reps = [
            len(set(draws[i]["dezenas"]) & set(draws[i - 1]["dezenas"]))
            for i in range(1, n)
        ]
        obs = Counter(reps)
        saida.append(
            {
                "chave": "repetidas_anterior",
                "label": analysis.label("repetidas_anterior", loteria),
                "tamanho_conjunto": sorteadas,
                "media_observada": round(sum(reps) / len(reps), 2),
                "media_teorica": round(sorteadas * sorteadas / total, 2),
                "linhas": [
                    {
                        "valor": x,
                        "observado_pct": round(100 * obs.get(x, 0) / len(reps), 2),
                        "teorico_pct": round(100 * teorico(sorteadas, x), 2),
                    }
                    for x in range(sorteadas + 1)
                    if obs.get(x, 0) or teorico(sorteadas, x) > 0.001
                ],
            }
        )

    somas = [sum(d["dezenas"]) for d in draws]
    var_pool = (total * total - 1) / 12
    dp_teorico = (sorteadas * var_pool * (total - sorteadas) / (total - 1)) ** 0.5
    return {
        "draws_considered": n,
        "indicadores": saida,
        "soma": {
            "media_observada": round(sum(somas) / len(somas), 1),
            "media_teorica": round(sorteadas * (cfg["min_num"] + cfg["max_num"]) / 2, 1),
            "desvio_observado": round(pstdev(somas), 1) if len(somas) > 1 else 0.0,
            "desvio_teorico": round(dp_teorico, 1),
            "min": min(somas),
            "max": max(somas),
        },
    }


def xray(draws: list[dict], concurso: int, loteria: str = "mega") -> dict:
    """Raio-X honesto de um sorteio: onde cada dezena sorteada estava no
    ranking de frequência e de atraso NA VÉSPERA daquele concurso — e quanto
    as estratégias 'quentes'/'atrasadas' teriam acertado.

    O tamanho dos conjuntos comparados (`hot6`/`overdue6`) acompanha a aposta
    simples da loteria: 6 na Mega, 15 na Lotofácil."""
    cfg = lotteries.get_loteria(loteria)
    pool = lotteries.numbers(cfg)
    escolher = cfg["escolher"]

    idx = next((i for i, d in enumerate(draws) if d["concurso"] == concurso), None)
    if idx is None:
        raise ValueError(f"concurso {concurso} não está no cache local")
    if idx == 0:
        raise ValueError("o primeiro concurso não tem histórico anterior para analisar")

    prior = draws[:idx]
    target = draws[idx]

    counts = Counter()
    for d in prior:
        counts.update(d["dezenas"])
    # ranking de frequência (1 = mais sorteado até então)
    by_freq = sorted(pool, key=lambda n: (-counts.get(n, 0), n))
    rank = {n: i + 1 for i, n in enumerate(by_freq)}

    delay_info = {d["n"]: d["delay"] for d in current_delays(prior, pool)["delays"]}
    by_delay = sorted(pool, key=lambda n: (-delay_info[n], n))

    hot6 = set(by_freq[:escolher])
    overdue6 = set(by_delay[:escolher])
    drawn = set(target["dezenas"])

    dezenas = [
        {
            "n": n,
            "freq_before": counts.get(n, 0),
            "freq_rank": rank[n],
            "delay_before": delay_info[n],
        }
        for n in target["dezenas"]
    ]
    return {
        "concurso": target["concurso"],
        "data": target["data"],
        "prior_draws": len(prior),
        "dezenas": dezenas,
        "soma": sum(target["dezenas"]),
        "pares": sum(1 for n in target["dezenas"] if n % 2 == 0),
        "hot6": sorted(hot6),
        "hot6_matches": len(drawn & hot6),
        "overdue6": sorted(overdue6),
        "overdue6_matches": len(drawn & overdue6),
    }
