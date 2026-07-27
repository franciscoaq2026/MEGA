"""Estratégias de geração de jogos e fechamentos.

Aviso honesto (que o app também exibe): nenhuma estratégia muda a
probabilidade de acerto — todas as combinações de k dezenas são igualmente
prováveis. As estratégias existem como exploração/entretenimento; a opção
anti-rateio não aumenta a chance de ganhar, apenas evita combinações
POPULARES (se um prêmio vier, divide-se com menos gente).

A ÚNICA coisa aqui que muda a probabilidade de verdade é jogar mais dezenas
(fechamento): uma aposta de k dezenas equivale a C(k, escolher) apostas
simples — e custa proporcionalmente a isso. Ver `odds()`.

Tudo é parametrizado pela loteria; nada assume "6 de 60".
"""

import random
from collections import Counter
from itertools import combinations
from math import comb, sqrt

from . import analysis, lotteries

ESTRATEGIAS = {
    "aleatorio": "Aleatório puro — sem viés nenhum (baseline)",
    "frequencia": "Ponderado por frequência — números historicamente mais sorteados pesam mais",
    "atrasados": "Atrasados — prioriza números que não saem há mais tempo",
    "balanceado": "Balanceado — metade quentes/metade frios, pares/ímpares equilibrados e soma perto da média",
}


def _numbers(loteria="mega") -> list[int]:
    return lotteries.numbers(lotteries.get_loteria(loteria))


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
    numbers = numbers or _numbers()
    return sorted(rng.sample(numbers, k))


def frequencia(rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None) -> list[int]:
    numbers = numbers or _numbers()
    counts = _freq_counts(draws)
    return _weighted_sample(rng, {n: counts.get(n, 0) + 1 for n in numbers}, k)


def atrasados(rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None) -> list[int]:
    numbers = numbers or _numbers()
    delays = _delays_pool(draws, numbers)
    return _weighted_sample(rng, {n: delays[n] + 1 for n in numbers}, k)


def _sum_tolerance(n_pool: int, k: int) -> float:
    """Tolerância da soma no gerador balanceado ≈ 1 desvio-padrão teórico.

    Amostragem sem reposição de k valores num pool 1..N:
        var(soma) = k · (N²-1)/12 · (N-k)/(N-1)

    Mega (6 de 60) dá ~41 (a constante que o código usava antes); Lotofácil
    (15 de 25) dá ~18 — usar 42 fixo lá dentro não filtraria nada, porque a
    soma inteira da Lotofácil varia só de 120 a 270."""
    if n_pool < 2 or k < 1:
        return 0.0
    var_pool = (n_pool * n_pool - 1) / 12
    var = k * var_pool * (n_pool - k) / (n_pool - 1)
    return sqrt(var)


def balanceado(
    rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None, max_tries: int = 400
) -> list[int]:
    numbers = numbers or _numbers()
    counts = _freq_counts(draws)
    ordered = sorted(numbers, key=lambda n: (-counts.get(n, 0), n))
    metade = len(numbers) // 2
    hot, cold = ordered[:metade], ordered[metade:]

    centro_num = (numbers[0] + numbers[-1]) / 2  # meio do intervalo
    sum_center = centro_num * k
    sum_tol = _sum_tolerance(len(numbers), k)
    min_evens = max(0, k // 2 - 1)
    max_evens = min(k, (k + 1) // 2 + 1)

    best: list[int] | None = None
    best_gap = float("inf")
    for _ in range(max_tries):
        n_hot = k // 2 + rng.choice([0, k % 2])
        n_hot = min(n_hot, len(hot))
        n_cold = k - n_hot
        if n_cold > len(cold):
            n_cold = len(cold)
            n_hot = k - n_cold
        candidate = sorted(rng.sample(hot, n_hot) + rng.sample(cold, n_cold))
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


def padrao_popular(
    dezenas: list[int],
    premiadas_passadas: set[tuple] | None = None,
    loteria="mega",
) -> list[str]:
    """Detecta padrões que MUITA gente joga (risco de rateio dividido).

    Cada regra só entra quando faz sentido na loteria: "todas até 31" não diz
    nada na Lotofácil (o volante vai só até 25, então TODO jogo cumpriria), e
    "mesma coluna" depende da largura do volante."""
    cfg = lotteries.get_loteria(loteria) if not isinstance(loteria, dict) else loteria
    cols = cfg["cols"]
    escolher = cfg["escolher"]
    motivos: list[str] = []
    ds = sorted(dezenas)
    if cfg["max_num"] > 31 and all(n <= 31 for n in ds):
        motivos.append("todas as dezenas até 31 (datas de aniversário)")
    diffs = {b - a for a, b in zip(ds, ds[1:])}
    if len(ds) > 2 and len(diffs) == 1:
        motivos.append("sequência aritmética (desenho no volante)")
    else:
        run = maior_sequencia_consecutiva(ds)
        if run >= cfg["consecutivos_populares"]:
            motivos.append(f"{run} números consecutivos")
    if len(ds) <= cols and len({(n - cfg["min_num"]) % cols for n in ds}) == 1:
        motivos.append("todos na mesma coluna do volante")
    if premiadas_passadas and len(ds) == escolher and tuple(ds) in premiadas_passadas:
        motivos.append("combinação que já foi premiada (muita gente repete jogos premiados)")
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
    espalhar: bool = False,
) -> list[dict]:
    """Gera `jogos` apostas pela estratégia escolhida.

    `espalhar` faz cada novo jogo ser o candidato que MENOS se sobrepõe aos já
    gerados. Só considera os jogos do MESMO pedido — nunca as apostas salvas
    pelo usuário.

    Medido por enumeração exata dos 3.268.760 sorteios da Lotofácil, 5 jogos:

                      ganha algo   retorno médio   ganha em 2+ bilhetes
        independente      44,65%         R$ 4,49                  7,98%
        espalhado         47,35%         R$ 4,49                  5,45%

    Ou seja: espalhar REDISTRIBUI, não aumenta. Ganha-se algo um pouco mais
    vezes e ganha-se em vários bilhetes um pouco menos vezes; o retorno médio
    é idêntico, porque a esperança da soma de N bilhetes é N vezes a de um,
    independentemente da correlação entre eles. A chance do prêmio principal
    também não muda: são N em C(total, escolher) de qualquer jeito.

    É, portanto, preferência de formato — não vantagem."""
    cfg = lotteries.get_loteria(loteria)
    numbers = lotteries.numbers(cfg)
    rng = rng or random.Random()
    gerador = GERADORES[estrategia]
    premiadas = {tuple(sorted(d["dezenas"])) for d in draws}
    resultado = []
    vistos: set[tuple] = set()
    escolhidos: list[set[int]] = []

    for _ in range(jogos):
        jogo, motivos = None, []
        melhor, melhor_sobrep = None, None
        # Quantos candidatos considerar antes de escolher. Sem espalhar, o
        # primeiro válido serve; espalhando, olhamos vários e ficamos com o
        # mais distante dos jogos que já saíram.
        tentativas = 120 if (espalhar and escolhidos) else 60
        for _tent in range(tentativas):
            cand = gerador(rng, draws, dezenas, numbers)
            cand_motivos = padrao_popular(cand, premiadas, cfg)
            if tuple(cand) in vistos:
                continue
            if anti_rateio and cand_motivos:
                continue
            if not (espalhar and escolhidos):
                jogo, motivos = cand, cand_motivos
                break
            sobrep = max(len(set(cand) & e) for e in escolhidos)
            if melhor_sobrep is None or sobrep < melhor_sobrep:
                melhor, melhor_sobrep, motivos = cand, sobrep, cand_motivos
                if sobrep == 0:
                    break
        if jogo is None:
            # espalhando, ou nenhum candidato passou nos filtros: usa o melhor
            jogo = melhor or gerador(rng, draws, dezenas, numbers)
            motivos = motivos if melhor else padrao_popular(jogo, premiadas, cfg)

        vistos.add(tuple(jogo))
        escolhidos.append(set(jogo))
        item = {
            "dezenas": jogo,
            "soma": sum(jogo),
            "pares": sum(1 for n in jogo if n % 2 == 0),
            "padroes_populares": motivos,
        }
        if espalhar and len(escolhidos) > 1:
            item["max_repetidas_dos_outros"] = max(
                len(set(jogo) & e) for e in escolhidos[:-1]
            )
        resultado.append(item)
    return resultado


def odds_carteira(n_jogos: int, loteria: str = "mega") -> dict:
    """Probabilidade acumulada de N apostas simples SEPARADAS.

    Para cada faixa, a chance de pelo menos uma das N apostas bater. Como a
    chance marginal é a mesma para qualquer sorteio, apostas distintas se
    comportam como ensaios independentes: P = 1 - (1-p)^N. Vale exatamente
    para o prêmio principal; para "ganhar algo" é o piso, porque espalhar os
    jogos melhora esse número (ver `gerar(espalhar=True)`)."""
    cfg = lotteries.get_loteria(loteria)
    base = odds(cfg["escolher"], cfg["preco"], loteria)
    faixas = {}
    for nome, f in base["faixas"].items():
        p = 1 - (1 - f["prob"]) ** n_jogos
        faixas[nome] = {"prob": p, "one_in": round(1 / p) if p else None}
    p_uma = sum(f["prob"] for f in base["faixas"].values())
    qualquer = 1 - (1 - p_uma) ** n_jogos
    return {
        "jogos": n_jogos,
        "dezenas": cfg["escolher"],
        "custo_estimado": round(n_jogos * cfg["preco"], 2),
        "faixas": faixas,
        "qualquer": {
            "prob": qualquer,
            "one_in": round(1 / qualquer, 2) if qualquer else None,
            "pct": round(100 * qualquer, 2),
        },
    }


def _passa_filtros(
    dezenas: list[int], filtros: dict, anterior: list[int] | None, loteria="mega"
) -> bool:
    m = analysis.metrics(dezenas, anterior, loteria)

    def faixa(chave: str, valor) -> bool:
        rng = filtros.get(chave)
        if not rng:
            return True
        lo, hi = rng
        return (lo is None or valor >= lo) and (hi is None or valor <= hi)

    for chave in ("soma", "pares", "primos", "moldura", "miolo", "baixas", "multiplos_3"):
        if not faixa(chave, m[chave]):
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
    loteria: str = "mega",
) -> dict:
    """Gera jogos que passam por TODOS os filtros ativos (rejection sampling).

    incluir: dezenas fixas em todo jogo. excluir: dezenas proibidas.
    Retorna os jogos e um relatório (quantas tentativas, se afrouxou)."""
    cfg = lotteries.get_loteria(loteria)
    rng = rng or random.Random()
    filtros = filtros or {}
    incluir = sorted(set(incluir or []))
    excluir = set(excluir or [])
    if set(incluir) & excluir:
        raise ValueError("uma dezena não pode estar em incluir e excluir ao mesmo tempo")
    if len(incluir) > dezenas:
        raise ValueError("mais dezenas fixas do que o tamanho do jogo")

    pool = [n for n in lotteries.numbers(cfg) if n not in excluir and n not in incluir]
    faltam = dezenas - len(incluir)
    if faltam > len(pool):
        raise ValueError("dezenas fixas/excluídas incompatíveis com o tamanho do jogo")

    anterior = draws[-1]["dezenas"] if draws else None
    premiadas = {tuple(sorted(d["dezenas"])) for d in draws}
    resultado: list[dict] = []
    vistos: set[tuple] = set()
    tentativas = 0

    while len(resultado) < jogos and tentativas < max_tentativas:
        tentativas += 1
        jogo = sorted(incluir + rng.sample(pool, faltam))
        chave = tuple(jogo)
        if chave in vistos:
            continue
        if not _passa_filtros(jogo, filtros, anterior, cfg):
            continue
        motivos = padrao_popular(jogo, premiadas, cfg)
        if anti_rateio and motivos:
            continue
        vistos.add(chave)
        m = analysis.metrics(jogo, anterior, cfg)
        resultado.append({"dezenas": jogo, "metrics": m, "padroes_populares": motivos})

    return {
        "jogos": resultado,
        "solicitados": jogos,
        "gerados": len(resultado),
        "tentativas": tentativas,
        "filtros_muito_restritivos": len(resultado) < jogos,
    }


def _guarantee_table(k: int, cfg: dict) -> list[dict]:
    """Roda completa de k dezenas (todas as C(k, escolher) apostas): se H das
    suas k dezenas forem sorteadas, existe uma aposta com exatamente H acertos."""
    faixas = cfg["faixas"]
    tabela = []
    for h in sorted(faixas, reverse=True):
        if h < 1 or h > cfg["escolher"]:
            continue
        tabela.append(
            {
                "acertos_entre_suas": h,
                "garante": faixas[h],
                "explicacao": f"se {h} das suas {k} dezenas saírem, você garante {faixas[h]}",
            }
        )
    return tabela


def roda_completa(dezenas: list[int], loteria: str = "mega") -> dict:
    cfg = lotteries.get_loteria(loteria)
    escolher = cfg["escolher"]
    k = len(dezenas)
    jogos = [sorted(c) for c in combinations(sorted(dezenas), escolher)]
    return {
        "tipo": "completa",
        "dezenas_escolhidas": sorted(dezenas),
        "num_jogos": len(jogos),
        "custo_estimado": round(len(jogos) * cfg["preco"], 2),
        "garantias": _guarantee_table(k, cfg),
        "jogos": jogos,
    }


def fechamento_reduzido(dezenas: list[int], garantia: int, loteria: str = "mega") -> dict:
    """Fechamento reduzido: menos apostas que a roda completa, garantindo pelo
    menos `garantia` acertos SE as dezenas sorteadas estiverem entre as suas
    escolhidas. Cobertura gulosa (com bitmask p/ velocidade) + verificação
    honesta da garantia."""
    cfg = lotteries.get_loteria(loteria)
    escolher = cfg["escolher"]
    ds = sorted(dezenas)
    k = len(ds)
    combos = [frozenset(c) for c in combinations(ds, escolher)]
    # alvos == candidatos (todos os subconjuntos de tamanho `escolher`)
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
    return {
        "tipo": "reduzida",
        "dezenas_escolhidas": ds,
        "num_jogos": len(escolhidas),
        "custo_estimado": round(len(escolhidas) * cfg["preco"], 2),
        "garantia_acertos": garantia,
        "garantia_faixa": cfg["faixas"].get(garantia, f"{garantia} acertos"),
        "garantia_verificada": garantido,
        "num_jogos_roda_completa": comb(k, escolher),
        "jogos": [sorted(combos[i]) for i in escolhidas],
    }


def odds(k: int, preco_simples: float | None = None, loteria: str = "mega") -> dict:
    """Probabilidades exatas (hipergeométrica) para um jogo de k dezenas.

    É o único lugar do app onde a probabilidade REALMENTE muda: uma aposta de
    k dezenas vale C(k, escolher) apostas simples — e custa o mesmo tanto.

    Mega: 20 dezenas = C(20,6) = 38.760 combinações → sena 1 em ~1.292.
    Lotofácil: 18 dezenas = C(18,15) = 816 combinações → 15 acertos 1 em ~4.006.
    """
    cfg = lotteries.get_loteria(loteria)
    total, sorteadas, escolher = cfg["total"], cfg["sorteadas"], cfg["escolher"]
    preco = cfg["preco"] if preco_simples is None else preco_simples
    denom = comb(total, k)
    faixas = {}
    for acertos, nome in sorted(cfg["faixas"].items(), reverse=True):
        if k - acertos < 0 or total - sorteadas < k - acertos:
            continue
        favoraveis = comb(sorteadas, acertos) * comb(total - sorteadas, k - acertos)
        p = favoraveis / denom
        faixas[nome] = {"prob": p, "one_in": round(1 / p) if p else None}
    combos = comb(k, escolher)
    qualquer = sum(f["prob"] for f in faixas.values())
    return {
        "dezenas": k,
        "combos_simples": combos,
        "custo_estimado": round(combos * preco, 2),
        "preco_simples": preco,
        "faixas": faixas,
        "qualquer": {
            "prob": qualquer,
            "one_in": round(1 / qualquer, 2) if qualquer else None,
            "pct": round(100 * qualquer, 2),
        },
        # O mesmo dinheiro gasto em bilhetes simples SEPARADOS. O prêmio
        # principal fica idêntico; "ganhar algo" muda muito, porque bilhetes
        # avulsos se espalham e a aposta múltipla concentra.
        "equivalente_simples": odds_carteira(combos, loteria)["qualquer"]
        if k > escolher
        else None,
    }


def distribuicao_acertos(k: int, loteria: str = "mega") -> dict:
    """Distribuição do nº de acertos de UMA aposta de k dezenas.

    É a mesma hipergeométrica de `odds()`, olhada por outro ângulo: em vez de
    "qual a chance da faixa X", responde "quantos acertos esperar". Serve para
    julgar um resultado já saído — sem essa régua, 9 acertos na Lotofácil
    parece ótimo, quando é exatamente a média.

        esperado = k · sorteadas / total
        var      = k · p · (1-p) · (total-k)/(total-1),  p = sorteadas/total

    Lotofácil, aposta simples: esperado 9,00 e desvio 1,22 — ou seja, quase
    todo jogo cai entre 7 e 11 acertos, e só a ponta ≥ 11 paga algo.
    Mega, aposta simples: esperado 0,60 — acertar 1 dezena já é acima da média.

    `p_menos`/`p_mais` são as caudas ESTRITAS (P(X < h) e P(X > h)), o que
    permite dizer honestamente quantos jogos fariam pior e melhor."""
    cfg = lotteries.get_loteria(loteria)
    total, sorteadas = cfg["total"], cfg["sorteadas"]
    faixas = cfg["faixas"]
    denom = comb(total, k)
    probs = {
        h: comb(sorteadas, h) * comb(total - sorteadas, k - h) / denom
        for h in range(0, min(sorteadas, k) + 1)
        if total - sorteadas >= k - h
    }
    p = sorteadas / total
    esperado = k * p
    var = k * p * (1 - p) * (total - k) / (total - 1) if total > 1 else 0.0
    acumulado = 0.0
    linhas = []
    for h in sorted(probs):
        linhas.append(
            {
                "acertos": h,
                "prob": probs[h],
                "pct": round(100 * probs[h], 4),
                "p_menos": acumulado,
                "p_mais": max(0.0, 1 - acumulado - probs[h]),
                "faixa": faixas.get(h),
            }
        )
        acumulado += probs[h]
    menor_faixa = min(faixas) if faixas else None
    premiado = sum(pr for h, pr in probs.items() if menor_faixa is not None and h >= menor_faixa)
    return {
        "loteria": cfg["code"],
        "dezenas": k,
        "esperado": round(esperado, 4),
        "desvio": round(sqrt(var), 4),
        "mais_provavel": max(probs, key=lambda h: probs[h]),
        "menor_faixa_premiada": menor_faixa,
        "premiado": {
            "prob": premiado,
            "pct": round(100 * premiado, 4),
            "one_in": round(1 / premiado) if premiado else None,
        },
        "linhas": linhas,
    }


def avaliar_acertos(acertos: int, k: int, loteria: str = "mega") -> dict:
    """Situa um resultado JÁ SAÍDO na distribuição do acaso.

    O veredito usa 1 desvio-padrão como régua: dentro de esperado ± desvio é
    "típico" — o que o acaso produz na maior parte das vezes. Não é elogio nem
    crítica ao jogo: como todas as combinações têm a mesma chance, ficar acima
    ou abaixo é só onde a moeda caiu naquele concurso."""
    d = distribuicao_acertos(k, loteria)
    linha = next((l for l in d["linhas"] if l["acertos"] == acertos), None)
    esperado, desvio = d["esperado"], d["desvio"]
    diff = acertos - esperado
    if desvio and diff > desvio:
        nivel, veredito = "acima", "acima do esperado"
    elif desvio and diff < -desvio:
        nivel, veredito = "abaixo", "abaixo do esperado"
    else:
        nivel, veredito = "tipico", "dentro do esperado"
    return {
        "dezenas": k,
        "acertos": acertos,
        "esperado": esperado,
        "desvio": desvio,
        "diferenca": round(diff, 4),
        "nivel": nivel,
        "veredito": veredito,
        "faixa_tipica": [
            max(0, round(esperado - desvio, 1)),
            round(esperado + desvio, 1),
        ],
        "pct_exato": linha["pct"] if linha else 0.0,
        "pct_pior": round(100 * linha["p_menos"], 2) if linha else None,
        "pct_melhor": round(100 * linha["p_mais"], 2) if linha else None,
        "premiado": d["premiado"],
        "menor_faixa_premiada": d["menor_faixa_premiada"],
    }


def garantia_minima(k: int, cfg: dict) -> int:
    """Acertos que uma aposta de k dezenas garante SEMPRE, por casa dos pombos.

    São `sorteadas` dezenas tiradas de `total`; ao marcar k, sobram total-k sem
    marcar, e no máximo essas podem ficar de fora do seu bilhete. Logo:

        garantido = k + sorteadas - total

    Na Mega dá negativo (6+6-60): marcar 6 de 60 não garante acerto nenhum.
    Na Lotofácil dá k-10 — e é uma propriedade forte da modalidade: 20 dezenas
    garantem 10 acertos em qualquer sorteio. Note que 10 é exatamente UM a
    menos que a faixa mínima premiada (11): garantir prêmio exigiria 21
    dezenas, acima do limite de 20 que a Caixa aceita."""
    return max(0, k + cfg["sorteadas"] - cfg["total"])


def _bilhetes_premiados(k: int, acertos: int, cfg: dict) -> float:
    """Nº médio de apostas simples, dentro de uma aposta de k dezenas, que
    fazem exatamente `acertos`.

    Uma aposta de k dezenas contém C(k, escolher) apostas simples. Se j das
    dezenas sorteadas caem entre as suas k, o número de apostas com exatamente
    `acertos` é C(j, acertos) x C(k-j, escolher-acertos). Somamos isso sobre
    todos os j, ponderado pela probabilidade de cada j."""
    total, sorteadas, escolher = cfg["total"], cfg["sorteadas"], cfg["escolher"]
    denom = comb(total, k)
    esperado = 0.0
    for j in range(acertos, min(sorteadas, k) + 1):
        if k - j < 0 or total - sorteadas < k - j:
            continue
        p = comb(sorteadas, j) * comb(total - sorteadas, k - j) / denom
        esperado += p * comb(j, acertos) * comb(k - j, escolher - acertos)
    return esperado


def odds_table(loteria: str = "mega") -> dict:
    """Tabela completa: para cada tamanho de aposta aceito pela Caixa, a chance
    de cada faixa, o custo, a chance de ganhar ALGUMA coisa e — onde a loteria
    tem prêmios fixos — quanto volta em média só por eles.

    O retorno fixo é uma constante da modalidade: como uma aposta de k dezenas
    é exatamente C(k, escolher) apostas simples, a fração que volta pelas
    faixas de valor fixo não muda com o tamanho da aposta."""
    cfg = lotteries.get_loteria(loteria)
    fixos = cfg.get("premios_fixos") or {}
    preco = cfg["preco"]
    menor_faixa = min(cfg["faixas"]) if cfg["faixas"] else None
    linhas = []
    for k in range(cfg["escolher"], cfg["max_escolher"] + 1):
        o = odds(k, preco, loteria)
        retorno_fixo = sum(_bilhetes_premiados(k, ac, cfg) * val for ac, val in fixos.items())
        garantido = garantia_minima(k, cfg)
        linhas.append(
            {
                **o,
                "retorno_fixo": {
                    "valor": round(retorno_fixo, 2),
                    "pct": round(100 * retorno_fixo / o["custo_estimado"], 2)
                    if o["custo_estimado"]
                    else 0.0,
                },
                "garantia_minima": {
                    "acertos": garantido,
                    "premia": menor_faixa is not None and garantido >= menor_faixa,
                },
            }
        )
    return {
        "loteria": cfg["code"],
        "nome": cfg["nome"],
        "preco_simples": preco,
        "premios_fixos": fixos,
        "rateio": cfg.get("rateio", {}),
        "linhas": linhas,
    }
