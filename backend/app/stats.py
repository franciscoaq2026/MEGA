"""Cálculos estatísticos sobre o histórico de sorteios.

Todas as funções recebem a lista de sorteios em ordem crescente de concurso
(como retornado por db.get_all_draws_asc) e são puras, para facilitar testes.

Nota honesta: nada aqui tem poder preditivo — cada sorteio é independente.
São ferramentas de exploração de dados.
"""

from collections import Counter
from itertools import combinations
from math import comb, sqrt
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
    honesto.

    Cada concurso tira `sorteadas` dezenas SEM repetir. Então a contagem de
    uma dezena varia n·p·(1−p), e não n·p como no qui-quadrado de Pearson, que
    supõe cada bola devolvida ao globo. Como as contagens somam sempre
    n·sorteadas, a soma ainda é multiplicada por (total−1)/total. Sem essa
    correção, a estatística média de um histórico 100% aleatório da Lotofácil
    era 10, e não 24: o teste praticamente nunca acusava desvio."""
    cfg = lotteries.get_loteria(loteria)
    pool = lotteries.numbers(cfg)
    n = len(draws)
    if n < 30:
        raise ValueError("histórico curto demais para o teste (mínimo 30 concursos)")

    counts = Counter()
    for d in draws:
        counts.update(d["dezenas"])
    p_dezena = cfg["sorteadas"] / cfg["total"]
    esperado = n * p_dezena
    variancia = n * p_dezena * (1 - p_dezena)
    if variancia <= 0:
        raise ValueError("a loteria sorteia todas as dezenas: não há o que testar")
    chi2 = (
        sum((counts.get(x, 0) - esperado) ** 2 for x in pool)
        / variancia
        * (cfg["total"] - 1)
        / cfg["total"]
    )
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
            "dos históricos aleatórios. Em sorteio físico, isso costuma vir de "
            "pequenas diferenças entre as bolas ou o equipamento. O efeito no "
            "acerto é pequeno: o botão “Qual estratégia usar?”, em Gerar jogos, "
            "testa se as dezenas mais sorteadas continuaram saindo mais, concurso "
            "a concurso, e quanto isso vale em acertos."
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


# z a partir do qual um sinal conta como confirmado: 2,5% numa ponta (o mesmo
# corte do intervalo de 95%).
Z_SINAL = 1.96


def _nivel_sinal(z: float) -> str:
    if z >= 3:
        return "claro"
    if z >= Z_SINAL:
        return "fraco"
    if z <= -Z_SINAL:
        return "contrario"
    return "nenhum"


def sinais_concurso_a_concurso(
    draws: list[dict], loteria: str = "mega", inicio: int = 100
) -> dict:
    """Testa, concurso a concurso e sem olhar o futuro, se o sinal de cada
    estratégia acertou o sorteio seguinte:

    - frequencia: quantas vezes cada dezena saiu até ali (o peso da Frequência);
    - atrasados: há quantos concursos cada dezena não sai (o peso dos Atrasados).

    Em cada concurso, soma o sinal (menos a média) das dezenas que saíram. Num
    sorteio honesto essa soma tem média zero e variância conhecida — a de tirar
    `sorteadas` dezenas sem repetir —, seja qual for o passado. Somando todos os
    concursos, z = soma / raiz(variância total) segue a normal padrão: z ≥ 1,96
    quer dizer que as dezenas favorecidas pelo sinal saíram mais do que o acaso
    explica. Tudo usa só o histórico anterior a cada concurso.

    `acertos_jogo` traduz isso em acertos: a média do jogo montado, em cada
    concurso, com as `escolher` dezenas de sinal mais alto até ali."""
    cfg = lotteries.get_loteria(loteria)
    pool = lotteries.numbers(cfg)
    sorteadas_por_concurso, total, k = cfg["sorteadas"], cfg["total"], cfg["escolher"]
    if len(draws) < inicio + 30:
        raise ValueError(
            f"histórico curto demais para o teste (mínimo {inicio + 30} concursos)"
        )

    contagem = {x: 0 for x in pool}
    ultima_vez: dict[int, int] = {}
    acum = {nome: {"soma": 0.0, "var": 0.0, "acertos": 0, "n": 0} for nome in ("frequencia", "atrasados")}
    for i, d in enumerate(draws):
        sorteadas = set(d["dezenas"])
        if i >= inicio:
            sinais = {
                "frequencia": contagem,
                "atrasados": {x: i - 1 - ultima_vez[x] if x in ultima_vez else i for x in pool},
            }
            for nome, sinal in sinais.items():
                media = sum(sinal.values()) / total
                var_pop = sum((v - media) ** 2 for v in sinal.values()) / total
                if var_pop == 0:
                    continue  # todas empatadas: o sinal não aponta dezena nenhuma
                a = acum[nome]
                a["soma"] += sum(sinal[x] for x in sorteadas) - sorteadas_por_concurso * media
                a["var"] += (
                    sorteadas_por_concurso * var_pop * (total - sorteadas_por_concurso) / (total - 1)
                )
                jogo = sorted(pool, key=lambda x: (-sinal[x], x))[:k]
                a["acertos"] += len(sorteadas.intersection(jogo))
                a["n"] += 1
        for x in sorteadas:
            contagem[x] += 1
            ultima_vez[x] = i

    p = sorteadas_por_concurso / total
    esperado = k * p
    desvio = sqrt(k * p * (1 - p) * (total - k) / (total - 1))
    resultado = {}
    for nome, a in acum.items():
        z = a["soma"] / sqrt(a["var"]) if a["var"] else 0.0
        resultado[nome] = {
            "z": round(z, 2),
            "nivel": _nivel_sinal(z),
            "concursos": a["n"],
            "acertos_jogo": round(a["acertos"] / a["n"], 3) if a["n"] else esperado,
            "esperado": round(esperado, 3),
            # quanto a média do jogo varia só por sorte nesses concursos (95%)
            "margem": round(1.96 * desvio / sqrt(a["n"]), 3) if a["n"] else None,
        }
    return {
        "concursos_testados": len(draws) - inicio,
        "primeiro_testado": draws[inicio]["concurso"],
        "ultimo_concurso": draws[-1]["concurso"],
        "ultima_data": draws[-1]["data"],
        "sinais": resultado,
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
