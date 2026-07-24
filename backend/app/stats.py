"""Cálculos estatísticos sobre o histórico de sorteios.

Todas as funções recebem a lista de sorteios em ordem crescente de concurso
(como retornado por db.get_all_draws_asc) e são puras, para facilitar testes.

Nota honesta: nada aqui tem poder preditivo — cada sorteio é independente.
São ferramentas de exploração de dados.
"""

from collections import Counter
from itertools import combinations
from math import comb

from . import lotteries

NUMBERS = range(1, 61)

# Valores teóricos de referência (jogo de 6 dezenas em 60)
TOTAL_COMBOS = comb(60, 6)  # 50.063.860
THEORETICAL_SUM_MEAN = 183.0  # 6 * média(1..60) = 6 * 30,5


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
