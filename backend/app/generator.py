"""Estratégias de geração de jogos.

Aviso honesto (que o app também exibe): nenhuma estratégia muda a
probabilidade de acerto — todas as combinações de k dezenas são igualmente
prováveis. As estratégias existem como exploração/entretenimento; a opção
anti-rateio não aumenta a chance de ganhar, apenas evita combinações
POPULARES (se um prêmio vier, divide-se com menos gente).
"""

import random
from collections import Counter
from itertools import combinations
from math import comb

from . import analysis
from .stats import current_delays

NUMBERS = list(range(1, 61))

ESTRATEGIAS = {
    "aleatorio": "Aleatório puro — sem viés nenhum (baseline)",
    "frequencia": "Ponderado por frequência — números historicamente mais sorteados pesam mais",
    "atrasados": "Atrasados — prioriza números que não saem há mais tempo",
    "balanceado": "Balanceado — metade quentes/metade frios, pares/ímpares equilibrados e soma perto da média",
}


def _weighted_sample(rng: random.Random, weights: dict[int, float], k: int) -> list[int]:
    pool = dict(weights)
    picked: list[int] = []
    for _ in range(k):
        ns = list(pool)
        chosen = rng.choices(ns, weights=[pool[n] for n in ns], k=1)[0]
        picked.append(chosen)
        del pool[chosen]
    return sorted(picked)


def _freq_counts(draws: list[dict]) -> Counter:
    counts: Counter = Counter()
    for d in draws:
        counts.update(d["dezenas"])
    return counts


def _delays_pool(draws: list[dict], numbers: list[int]) -> dict[int, int]:
    """Atraso (concursos desde a última aparição) de cada número do pool,
    calculado direto dos sorteios — genérico para qualquer loteria."""
    last_seen: dict[int, int] = {}
    for i, d in enumerate(draws):
        for n in d["dezenas"]:
            last_seen[n] = i
    total = len(draws)
    return {n: (total - 1 - last_seen[n]) if n in last_seen else total for n in numbers}


def aleatorio(rng: random.Random, _draws: list[dict], k: int, numbers: list[int] | None = None) -> list[int]:
    numbers = numbers or NUMBERS
    return sorted(rng.sample(numbers, k))


def frequencia(rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None) -> list[int]:
    numbers = numbers or NUMBERS
    counts = _freq_counts(draws)
    return _weighted_sample(rng, {n: counts.get(n, 0) + 1 for n in numbers}, k)


def atrasados(rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None) -> list[int]:
    numbers = numbers or NUMBERS
    delays = _delays_pool(draws, numbers)
    return _weighted_sample(rng, {n: delays[n] + 1 for n in numbers}, k)


def balanceado(
    rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None, max_tries: int = 400
) -> list[int]:
    numbers = numbers or NUMBERS
    counts = _freq_counts(draws)
    ordered = sorted(numbers, key=lambda n: (-counts.get(n, 0), n))
    metade = len(numbers) // 2
    hot, cold = ordered[:metade], ordered[metade:]

    centro_num = (numbers[0] + numbers[-1]) / 2  # meio do intervalo
    sum_center = centro_num * k
    sum_tol = 7 * k  # p/ 6 dezenas: 183 ± 42
    min_evens = max(0, k // 2 - 1)
    max_evens = min(k, (k + 1) // 2 + 1)

    best: list[int] | None = None
    best_gap = float("inf")
    for _ in range(max_tries):
        n_hot = k // 2 + rng.choice([0, k % 2])
        candidate = sorted(rng.sample(hot, n_hot) + rng.sample(cold, k - n_hot))
        soma = sum(candidate)
        evens = sum(1 for n in candidate if n % 2 == 0)
        gap = abs(soma - sum_center)
        if gap < best_gap:
            best, best_gap = candidate, gap
        if min_evens <= evens <= max_evens and gap <= sum_tol:
            return candidate
    return best or sorted(rng.sample(numbers, k))


GERADORES = {
    "aleatorio": aleatorio,
    "frequencia": frequencia,
    "atrasados": atrasados,
    "balanceado": balanceado,
}


def padrao_popular(dezenas: list[int], senas_passadas: set[tuple] | None = None) -> list[str]:
    """Detecta padrões que MUITA gente joga (risco de rateio dividido)."""
    motivos: list[str] = []
    ds = sorted(dezenas)
    if all(n <= 31 for n in ds):
        motivos.append("todas as dezenas até 31 (datas de aniversário)")
    diffs = {b - a for a, b in zip(ds, ds[1:])}
    if len(diffs) == 1:
        motivos.append("sequência aritmética (desenho no volante)")
    else:
        run = maior_sequencia_consecutiva(ds)
        if run >= 4:
            motivos.append(f"{run} números consecutivos")
    if len({n % 10 for n in ds}) == 1:
        motivos.append("todos na mesma coluna do volante")
    if senas_passadas and len(ds) == 6 and tuple(ds) in senas_passadas:
        motivos.append("combinação que já foi sena (muita gente repete jogos premiados)")
    return motivos


def maior_sequencia_consecutiva(ds: list[int]) -> int:
    best = run = 1
    for a, b in zip(ds, ds[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    return best


def gerar(
    draws: list[dict],
    estrategia: str,
    jogos: int,
    dezenas: int,
    anti_rateio: bool = False,
    rng: random.Random | None = None,
    loteria: str = "mega",
) -> list[dict]:
    from . import lotteries

    cfg = lotteries.get_loteria(loteria)
    numbers = list(range(cfg["min_num"], cfg["max_num"] + 1))
    rng = rng or random.Random()
    gerador = GERADORES[estrategia]
    senas = {tuple(sorted(d["dezenas"])) for d in draws}
    resultado = []
    vistos: set[tuple] = set()
    for _ in range(jogos):
        jogo, motivos = None, []
        for _tent in range(60):
            jogo = gerador(rng, draws, dezenas, numbers)
            motivos = padrao_popular(jogo, senas)
            repetido = tuple(jogo) in vistos
            if not repetido and (not anti_rateio or not motivos):
                break
        vistos.add(tuple(jogo))
        resultado.append(
            {
                "dezenas": jogo,
                "soma": sum(jogo),
                "pares": sum(1 for n in jogo if n % 2 == 0),
                "padroes_populares": motivos,
            }
        )
    return resultado


def _passa_filtros(dezenas: list[int], filtros: dict, anterior: list[int] | None) -> bool:
    m = analysis.metrics(dezenas, anterior)

    def faixa(chave: str, valor) -> bool:
        rng = filtros.get(chave)
        if not rng:
            return True
        lo, hi = rng
        return (lo is None or valor >= lo) and (hi is None or valor <= hi)

    if not faixa("soma", m["soma"]):
        return False
    if not faixa("pares", m["pares"]):
        return False
    if not faixa("primos", m["primos"]):
        return False
    if not faixa("moldura", m["moldura"]):
        return False
    if not faixa("baixas", m["baixas"]):
        return False
    cons_max = filtros.get("consecutivos_max")
    if cons_max is not None and m["consecutivos"] > cons_max:
        return False
    if m["repetidas_anterior"] is not None and not faixa(
        "repetidas_anterior", m["repetidas_anterior"]
    ):
        return False
    return True


def gerar_avancado(
    draws: list[dict],
    jogos: int,
    dezenas: int,
    filtros: dict | None = None,
    incluir: list[int] | None = None,
    excluir: list[int] | None = None,
    anti_rateio: bool = False,
    rng: random.Random | None = None,
    max_tentativas: int = 20000,
) -> dict:
    """Gera jogos que passam por TODOS os filtros ativos (rejection sampling).

    incluir: dezenas fixas em todo jogo. excluir: dezenas proibidas.
    Retorna os jogos e um relatório (quantas tentativas, se afrouxou)."""
    rng = rng or random.Random()
    filtros = filtros or {}
    incluir = sorted(set(incluir or []))
    excluir = set(excluir or [])
    if set(incluir) & excluir:
        raise ValueError("uma dezena não pode estar em incluir e excluir ao mesmo tempo")
    if len(incluir) > dezenas:
        raise ValueError("mais dezenas fixas do que o tamanho do jogo")

    pool = [n for n in NUMBERS if n not in excluir and n not in incluir]
    faltam = dezenas - len(incluir)
    if faltam > len(pool):
        raise ValueError("dezenas fixas/excluídas incompatíveis com o tamanho do jogo")

    anterior = draws[-1]["dezenas"] if draws else None
    senas = {tuple(sorted(d["dezenas"])) for d in draws}
    resultado: list[dict] = []
    vistos: set[tuple] = set()
    tentativas = 0

    while len(resultado) < jogos and tentativas < max_tentativas:
        tentativas += 1
        jogo = sorted(incluir + rng.sample(pool, faltam))
        chave = tuple(jogo)
        if chave in vistos:
            continue
        if not _passa_filtros(jogo, filtros, anterior):
            continue
        motivos = padrao_popular(jogo, senas)
        if anti_rateio and motivos:
            continue
        vistos.add(chave)
        m = analysis.metrics(jogo, anterior)
        resultado.append({"dezenas": jogo, "metrics": m, "padroes_populares": motivos})

    return {
        "jogos": resultado,
        "solicitados": jogos,
        "gerados": len(resultado),
        "tentativas": tentativas,
        "filtros_muito_restritivos": len(resultado) < jogos,
    }


def _guarantee_table(k: int) -> list[dict]:
    """Roda completa de k dezenas (todas as C(k,6) apostas): se H das suas k
    dezenas forem sorteadas, existe uma aposta com exatamente H acertos."""
    tabela = []
    for h in range(6, 3, -1):
        faixa = {6: "sena", 5: "quina", 4: "quadra"}[h]
        tabela.append(
            {
                "acertos_entre_suas": h,
                "garante": faixa,
                "explicacao": f"se {h} das suas {k} dezenas saírem, você garante uma {faixa}",
            }
        )
    return tabela


def roda_completa(dezenas: list[int]) -> dict:
    k = len(dezenas)
    jogos = [sorted(c) for c in combinations(sorted(dezenas), 6)]
    return {
        "tipo": "completa",
        "dezenas_escolhidas": sorted(dezenas),
        "num_jogos": len(jogos),
        "custo_estimado": len(jogos) * 6.0,
        "garantias": _guarantee_table(k),
        "jogos": jogos,
    }


def fechamento_reduzido(dezenas: list[int], garantia: int) -> dict:
    """Fechamento reduzido: menos apostas que a roda completa, garantindo pelo
    menos `garantia` acertos SE as 6 dezenas sorteadas estiverem entre as suas
    escolhidas. Cobertura gulosa (com bitmask p/ velocidade) + verificação
    honesta da garantia. garantia ∈ {4, 5}."""
    ds = sorted(dezenas)
    k = len(ds)
    combos = [frozenset(c) for c in combinations(ds, 6)]
    # alvos == candidatos (todos os 6-subconjuntos das suas dezenas)
    # cobertura de cada candidato como bitmask sobre os índices dos alvos
    cov = []
    for ap in combos:
        mask = 0
        for j, alvo in enumerate(combos):
            if len(ap & alvo) >= garantia:
                mask |= 1 << j
        cov.append(mask)

    alvo_total = (1 << len(combos)) - 1
    faltam = alvo_total
    escolhidas: list[int] = []
    while faltam:
        melhor = max(range(len(combos)), key=lambda i: (cov[i] & faltam).bit_count())
        if (cov[melhor] & faltam) == 0:
            break
        escolhidas.append(melhor)
        faltam &= ~cov[melhor]

    garantido = faltam == 0
    faixa = {6: "sena", 5: "quina", 4: "quadra"}[garantia]
    return {
        "tipo": "reduzida",
        "dezenas_escolhidas": ds,
        "num_jogos": len(escolhidas),
        "custo_estimado": len(escolhidas) * 6.0,
        "garantia_acertos": garantia,
        "garantia_faixa": faixa,
        "garantia_verificada": garantido,
        "num_jogos_roda_completa": comb(k, 6),
        "jogos": [sorted(combos[i]) for i in escolhidas],
    }


def odds(k: int, preco_simples: float = 6.0) -> dict:
    """Probabilidades exatas (hipergeométrica) para um jogo de k dezenas.

    A Caixa aceita apostas de 6 a 20 dezenas (limite ampliado de 15 para 20).
    Ex.: 20 dezenas = C(20,6) = 38.760 combinações → sena em 1 a cada ~1.292
    concursos — é assim que os grandes bolões de lotérica "ganham sempre".
    """
    total = comb(60, k)
    faixas = {}
    for nome, m in (("sena", 6), ("quina", 5), ("quadra", 4)):
        favoraveis = comb(6, m) * comb(54, k - m)
        p = favoraveis / total
        faixas[nome] = {"prob": p, "one_in": round(1 / p) if p else None}
    combos = comb(k, 6)
    return {
        "dezenas": k,
        "combos_simples": combos,
        "custo_estimado": round(combos * preco_simples, 2),
        "preco_simples": preco_simples,
        "faixas": faixas,
    }
