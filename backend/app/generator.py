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
from bisect import bisect
from collections import Counter
from functools import lru_cache, partial
from itertools import accumulate, combinations
from math import comb, sqrt

from . import analysis, lotteries, stats

ESTRATEGIAS = {
    "aleatorio": "Aleatório puro — sem viés nenhum (baseline)",
    "frequencia": "Ponderado por frequência — números historicamente mais sorteados pesam mais",
    "atrasados": "Atrasados — prioriza números que não saem há mais tempo",
    "balanceado": "Balanceado — metade quentes/metade frios, pares/ímpares equilibrados e soma perto da média",
}


def _numbers(loteria="mega") -> list[int]:
    return lotteries.numbers(lotteries.get_loteria(loteria))


def _weighted_sample(rng: random.Random, weights: dict[int, float], k: int) -> list[int]:
    """Sorteia k dezenas sem repetição, cada uma com chance proporcional ao peso.

    Faz a mesma conta de `rng.choices(ns, weights=..., k=1)` a cada dezena (um
    random() e bisect nos pesos acumulados), então devolve exatamente os mesmos
    jogos para a mesma semente — só sem refazer dicionário e listas a cada
    passo. O Espalhar chama isto centenas de vezes por pedido, e o backtest com
    vários jogos por concurso, dezenas de milhares."""
    ns = list(weights)
    ws = [weights[n] for n in ns]
    picked: list[int] = []
    for _ in range(k):
        cum = list(accumulate(ws))
        i = bisect(cum, rng.random() * (cum[-1] + 0.0), 0, len(cum) - 1)
        picked.append(ns.pop(i))
        ws.pop(i)
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


# `counts`/`delays`: o resumo do histórico já calculado. O gerar() calcula uma
# vez por pedido; sem isso, cada candidato recontava o histórico inteiro.
def frequencia(
    rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None,
    counts: Counter | None = None,
) -> list[int]:
    numbers = numbers or _numbers()
    counts = _freq_counts(draws) if counts is None else counts
    return _weighted_sample(rng, {n: counts.get(n, 0) + 1 for n in numbers}, k)


def atrasados(
    rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None,
    delays: dict[int, int] | None = None,
) -> list[int]:
    numbers = numbers or _numbers()
    delays = _delays_pool(draws, numbers) if delays is None else delays
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


def ordem_por_frequencia(numbers: list[int], counts: Counter) -> list[int]:
    """Dezenas da mais para a menos sorteada (empate: a menor primeiro). A
    metade de cima são as "quentes" do Balanceado."""
    return sorted(numbers, key=lambda n: (-counts.get(n, 0), n))


def balanceado(
    rng: random.Random, draws: list[dict], k: int, numbers: list[int] | None = None, max_tries: int = 400,
    counts: Counter | None = None, ordem: list[int] | None = None,
) -> list[int]:
    numbers = numbers or _numbers()
    if ordem is None:
        counts = _freq_counts(draws) if counts is None else counts
        ordem = ordem_por_frequencia(numbers, counts)
    ordered = ordem
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


def piso_sobreposicao(k: int, cfg: dict) -> int:
    """Dezenas que dois bilhetes de k dezenas SEMPRE compartilham.

    Casa dos pombos, como em `garantia_minima`: dois bilhetes ocupam 2k lugares
    num volante de `total` dezenas, então pelo menos 2k - total têm de coincidir.

        piso = max(0, 2k - total)

    Na Mega dá 0 (6+6 < 60: dois jogos podem ser totalmente disjuntos). Na
    Lotofácil dá 5 — dois jogos de 15 dezenas em 25 NÃO PODEM dividir menos de
    5 dezenas, por mais que se tente espalhar. É o limite de quanto a opção
    "espalhar" pode entregar, e o motivo de ela render pouco lá."""
    return max(0, 2 * k - cfg["total"])


def limiar_sobreposicao(cfg: dict) -> int:
    """Sobreposição máxima que ainda não custa NADA em "levar algum prêmio".

    Dois bilhetes só podem premiar no MESMO sorteio se somarem 2·faixa_mínima
    acertos, e a soma dos acertos de dois bilhetes é no máximo
    `sobreposição + sorteadas` (as dezenas fora da interseção competem pelas
    mesmas bolas). Logo prêmio duplo só é possível a partir de
    `2·faixa_mínima − sorteadas`, e abaixo disso:

        P(levar algo em N bilhetes) = N · p, EXATAMENTE

    porque a inclusão-exclusão não tem termo para subtrair — nenhum par pode
    ganhar junto. É o teto: nenhuma disposição de N bilhetes supera N·p.

        limiar = 2·faixa_mínima − sorteadas − 1

    Mega: 1 (dividir 1 dezena é tão bom quanto dividir nenhuma). Lotofácil: 6
    — e como o piso lá é 5, dois bilhetes de 15 dezenas conseguem ficar na zona
    gratuita, o que explica por que sobreposição 5 e 6 dão a MESMA chance de
    premiar (21,178% = 2 × 10,589%)."""
    if not cfg["faixas"]:
        return -1
    return 2 * min(cfg["faixas"]) - cfg["sorteadas"] - 1


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
    historico: dict | None = None,
) -> list[dict]:
    """Gera `jogos` apostas pela estratégia escolhida.

    `historico` é o resumo de `draws` já pronto — "counts" (vezes que cada
    dezena saiu), "delays" (concursos sem sair) e "premiadas" (combinações já
    sorteadas) —, para quem gera muitas vezes sobre históricos que só crescem
    (o backtest) não recontar tudo a cada pedido. Sem ele, sai de `draws`.

    `espalhar` faz cada novo jogo ser o candidato que MENOS se sobrepõe aos já
    gerados. Só considera os jogos do MESMO pedido — nunca as apostas salvas
    pelo usuário.

    Medido por enumeração exata dos 3.268.760 sorteios da Lotofácil, 5 jogos
    (12 conjuntos gerados por linha; desvio entre conjuntos entre parênteses):

                              ganha algo   retorno médio   em 2+ bilhetes
        soltos (fórmula)          42,86%         R$ 4,49           9,02%
        gerados sem espalhar   43,1% (2,1)       R$ 4,49     8,8% (1,3)
        gerados espalhando     47,5% (0,6)       R$ 4,49     5,3% (0,6)

    Repare na dispersão: sem espalhar, o resultado depende muito de quais
    bilhetes saíram (38% a 46%); espalhando, a variação quase some. O retorno
    médio é exato e igual nos três — é 5 x 25,67% x R$ 3,50, e a esperança da
    soma não depende de correlação nenhuma.

    Ou seja: espalhar REDISTRIBUI, não aumenta. O número de bilhetes premiados
    por concurso varia menos: menos concursos sem nada e menos com muitos
    prêmios juntos (com 5 bilhetes isso inclui "2+"; com 20, não — 2+ sobe de
    64% para 70%, enquanto 5+ cai de 5,4% para 2,2%). O retorno médio é
    idêntico, porque a esperança da soma de N bilhetes é N vezes a de um,
    independentemente da correlação entre eles. A chance do prêmio principal
    também não muda: são N em C(total, escolher) de qualquer jeito.

    É, portanto, preferência de formato — não vantagem.

    Com 2 bilhetes o assunto se fecha em contas exatas: a distribuição conjunta
    dos acertos depende SÓ de quantas dezenas os dois compartilham — quais
    dezenas são não muda nada. Logo nenhuma estratégia mexe nisso; só a
    sobreposição mexe, e ela tem piso (ver `piso_sobreposicao`)."""
    cfg = lotteries.get_loteria(loteria)
    numbers = lotteries.numbers(cfg)
    rng = rng or random.Random()
    # O resumo do histórico (contagem ou atraso de cada dezena) sai uma vez por
    # pedido. Antes era refeito a cada candidato — até 120 por bilhete com o
    # Espalhar —, e 50 jogos pela Frequência levavam ~5 s.
    historico = historico or {}
    resumo = {}
    if estrategia in ("frequencia", "balanceado"):
        resumo["counts"] = historico["counts"] if "counts" in historico else _freq_counts(draws)
        if estrategia == "balanceado":
            # Quentes/frias não mudam dentro do pedido: ordenar uma vez, não
            # a cada um dos até 120 candidatos por jogo.
            resumo["ordem"] = ordem_por_frequencia(numbers, resumo["counts"])
    elif estrategia == "atrasados":
        resumo["delays"] = (
            historico["delays"] if "delays" in historico else _delays_pool(draws, numbers)
        )
    gerador = partial(GERADORES[estrategia], **resumo)
    premiadas = (
        historico["premiadas"]
        if "premiadas" in historico
        else {tuple(sorted(d["dezenas"])) for d in draws}
    )
    resultado = []
    vistos: set[tuple] = set()
    escolhidos: list[set[int]] = []
    # Melhor sobreposição alcançável. Buscar "zero repetidas" só faz sentido
    # onde 2k <= total (Mega); na Lotofácil o piso é 5 e mirar em 0 fazia o
    # laço gastar todos os candidatos sem nunca reconhecer o ótimo.
    piso = piso_sobreposicao(dezenas, cfg)

    for _ in range(jogos):
        jogo, motivos = None, []
        melhor, melhor_sobrep = None, None
        # Quantos candidatos considerar antes de escolher. Sem espalhar, o
        # primeiro válido serve; espalhando, olhamos vários e ficamos com o
        # mais distante dos jogos que já saíram.
        tentativas = 120 if (espalhar and escolhidos) else 60
        for _tent in range(tentativas):
            cand = gerador(rng, draws, dezenas, numbers)
            if tuple(cand) in vistos:
                continue
            # Os padrões só filtram com o anti-rateio; sem ele, saem no fim e
            # só para o jogo escolhido, não para cada um dos até 120 candidatos.
            cand_motivos = padrao_popular(cand, premiadas, cfg) if anti_rateio else None
            if anti_rateio and cand_motivos:
                continue
            if not (espalhar and escolhidos):
                jogo, motivos = cand, cand_motivos
                break
            sobrep = max(len(set(cand) & e) for e in escolhidos)
            if melhor_sobrep is None or sobrep < melhor_sobrep:
                melhor, melhor_sobrep, motivos = cand, sobrep, cand_motivos
                if sobrep <= piso:
                    break
        if jogo is None:
            # Espalhando, ou nenhum candidato passou nos filtros: fica com o
            # melhor que apareceu (esse já passou pelo `vistos` no laço acima).
            if melhor is not None:
                jogo = melhor
            else:
                # Nenhum candidato sobreviveu aos filtros: sorteia um novo, mas
                # ainda respeitando `vistos`. Bilhete repetido no mesmo lote é
                # dinheiro gasto sem cobrir nada de novo — antes este caminho
                # pulava a trava e podia emitir duplicata (reproduzido em 4% dos
                # lotes numa loteria sintética com o espaço quase esgotado).
                # Se nem assim sair inédito, as combinações realmente acabaram.
                for _ in range(200):
                    cand = gerador(rng, draws, dezenas, numbers)
                    if tuple(cand) not in vistos:
                        break
                jogo = cand
                motivos = padrao_popular(jogo, premiadas, cfg)
        if motivos is None:
            motivos = padrao_popular(jogo, premiadas, cfg)

        vistos.add(tuple(jogo))
        escolhidos.append(set(jogo))
        item = {
            "dezenas": jogo,
            "soma": sum(jogo),
            "pares": sum(1 for n in jogo if n % 2 == 0),
            "padroes_populares": motivos,
        }
        resultado.append(item)
    return resultado


def resumo_sobreposicao(jogos: list[dict], k: int, loteria: str = "mega") -> dict | None:
    """Quanto os bilhetes do pedido se repetem entre si, contra o piso teórico.

    É a única coisa que a escolha de dezenas pode mexer num conjunto de vários
    bilhetes: com 2 bilhetes, a distribuição conjunta dos acertos depende só da
    sobreposição, então "qual estratégia acerta mais" não tem resposta — "quão
    espalhados estão os bilhetes" tem.

    Verificado por enumeração exata dos 3.268.760 sorteios (2 bilhetes de 15):

        sobreposição    5 ou 6    9 (típico sem espalhar)    15 (bilhetes iguais)
        premiar em >=1  21,18%                     20,18%                 10,59%
        melhor bilhete    9,88                       9,68                   9,00
        retorno médio   R$ 1,80                    R$ 1,80                R$ 1,80

    O retorno médio não se move — espalhar redistribui, não aumenta.

    `sem_custo` é o que realmente importa, e é mais generoso que o piso: até
    `limiar_sobreposicao` a chance de levar algo já está no teto de N·p, então
    apertar mais a sobreposição não compra nada."""
    if len(jogos) < 2:
        return None
    cfg = lotteries.get_loteria(loteria)
    conjuntos = [set(j["dezenas"]) for j in jogos]
    pares = [
        len(a & b) for i, a in enumerate(conjuntos) for b in conjuntos[i + 1:]
    ]
    piso = piso_sobreposicao(k, cfg)
    limiar = limiar_sobreposicao(cfg)
    maxima = max(pares)
    return {
        "maxima": maxima,
        "media": round(sum(pares) / len(pares), 2),
        "piso": piso,
        "no_piso": maxima <= piso,
        "limiar": limiar,
        "sem_custo": maxima <= limiar,
        # Nenhum par PODE ficar abaixo do piso, então quando o piso já está na
        # zona gratuita o ótimo é sempre alcançável — vale dizer isso ao usuário.
        "otimo_possivel": piso <= limiar,
    }


def _overlap_maximo(bilhetes: list[set[int]]) -> int:
    """Maior sobreposição entre qualquer par do lote (0 se houver <2 bilhetes)."""
    n = len(bilhetes)
    if n < 2:
        return 0
    return max(
        len(bilhetes[i] & bilhetes[j]) for i in range(n) for j in range(i + 1, n)
    )


def qualquer_medido(
    bilhetes: list[set[int]], cfg: dict, trials: int = 60_000, rng: random.Random | None = None
) -> float:
    """P(ganhar QUALQUER prêmio) medida por simulação direta sobre os bilhetes
    DE VERDADE — sorteia `trials` resultados possíveis e conta em quantos
    algum bilhete bate a faixa mínima.

    Ao contrário de uma fórmula fechada, isto captura QUALQUER correlação
    entre bilhetes automaticamente (inclusive 3 ou mais ganhando juntos no
    mesmo sorteio), sem precisar assumir nada sobre como eles se sobrepõem —
    ao custo de ruído de amostragem, pequeno com `trials` na casa de 10⁴–10⁵
    (erro-padrão bem abaixo de 0,1 ponto percentual nas faixas de chance que
    aparecem aqui). É o último recurso de `chance_lote`: só entra onde a conta
    exata não converge rápido (Lotofácil, a partir de 4 bilhetes)."""
    rng = rng or random.Random()
    pool = lotteries.numbers(cfg)
    sorteadas = cfg["sorteadas"]
    min_faixa = min(cfg["faixas"])
    ganhou = 0
    for _ in range(trials):
        sorteio = set(rng.sample(pool, sorteadas))
        if any(len(b & sorteio) >= min_faixa for b in bilhetes):
            ganhou += 1
    return ganhou / trials


def _p_premiar(cfg: dict) -> float:
    """Chance de UM bilhete simples chegar à faixa mínima."""
    k, sd, total, m = cfg["escolher"], cfg["sorteadas"], cfg["total"], min(cfg["faixas"])
    return sum(comb(k, h) * comb(total - k, sd - h) for h in range(m, min(k, sd) + 1)) / comb(total, sd)


@lru_cache(maxsize=None)
def _par_premia_junto(o: int, k: int, m: int, sd: int, total: int) -> float:
    """P(dois bilhetes de k dezenas, com `o` em comum, fazerem m+ acertos no
    mesmo sorteio). Conta exata: as `sd` bolas sorteadas se repartem entre as
    dezenas em comum, as só de um, as só do outro e o resto do volante."""
    so, resto = k - o, total - (2 * k - o)
    casos = 0
    for s in range(min(o, sd) + 1):
        for a in range(min(so, sd - s) + 1):
            for b in range(min(so, sd - s - a) + 1):
                r = sd - s - a - b
                if r <= resto and s + a >= m and s + b >= m:
                    casos += comb(o, s) * comb(so, a) * comb(so, b) * comb(resto, r)
    return casos / comb(total, sd)


# Pedaços do diagrama de Venn de três bilhetes: (está em A, em B, em C).
_REGIOES_TRIO = ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (1, 1, 1))


@lru_cache(maxsize=None)
def _trio_premia_junto(tamanhos: tuple, m: int, sd: int, total: int) -> float:
    """P(três bilhetes fazerem m+ acertos no mesmo sorteio), dado o tamanho de
    cada pedaço do diagrama de Venn (na ordem de _REGIOES_TRIO)."""
    regioes = _REGIOES_TRIO + ((0, 0, 0),)
    tams = tamanhos + (total - sum(tamanhos),)
    casos = 0

    def reparte(i, faltam, prod, ha, hb, hc):
        nonlocal casos
        if i == len(regioes):
            if faltam == 0 and ha >= m and hb >= m and hc >= m:
                casos += prod
            return
        ea, eb, ec = regioes[i]
        for x in range(min(faltam, tams[i]) + 1):
            reparte(i + 1, faltam - x, prod * comb(tams[i], x), ha + x * ea, hb + x * eb, hc + x * ec)

    reparte(0, sd, 1, 0, 0, 0)
    return casos / comb(total, sd)


def chance_lote(
    bilhetes: list[set[int]], cfg: dict, rng: random.Random | None = None
) -> tuple[float, str]:
    """P(pelo menos um bilhete do lote chegar à faixa mínima), para um lote
    CONCRETO de apostas simples. Devolve (probabilidade, método).

    Inclusão-exclusão: P = S1 − S2 + S3 − …, em que Sk soma a chance de k
    bilhetes premiarem juntos. Só entram grupos em que TODO par divide mais
    dezenas que o limiar (`limiar_sobreposicao`) — os demais não premiam
    juntos nunca.

    1. Nenhum par passa do limiar: P = N·p, o teto ("exato").
    2. Até 3 bilhetes a série acaba em S3 e é exata; com mais, pelas
       desigualdades de Bonferroni S1 − S2 + S3 fica a menos de S3 da verdade
       — usada quando isso é desprezível. É o caso da Mega, em que premiar
       junto é raro: até 200 bilhetes o erro fica abaixo de 0,02 ponto
       ("combinatorio").
    3. Onde premiar junto é comum (Lotofácil, a partir de 4 bilhetes), a série
       não converge rápido: simulação de 60 mil sorteios ("simulado").

    Antes, a Mega acima de ~30 bilhetes caía na simulação, cujo ruído
    (±0,05 ponto) é maior que o próprio efeito do Espalhar nela: o painel
    chegava a mostrar o Espalhar REDUZINDO a chance com 40 e 50 bilhetes."""
    k, sd, total, m = cfg["escolher"], cfg["sorteadas"], cfg["total"], min(cfg["faixas"])
    n = len(bilhetes)
    teto = n * _p_premiar(cfg)  # Boole: P(união) <= soma das probabilidades
    limiar = limiar_sobreposicao(cfg)

    s2 = 0.0
    vizinhos: dict[int, set[int]] = {i: set() for i in range(n)}
    juntos: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            o = len(bilhetes[i] & bilhetes[j])
            if o > limiar:
                juntos[(i, j)] = _par_premia_junto(o, k, m, sd, total)
                s2 += juntos[(i, j)]
                vizinhos[i].add(j)
                vizinhos[j].add(i)
    if not juntos:
        return teto, "exato"

    trios = [
        (i, j, t)
        for i in range(n)
        for j in sorted(vizinhos[i])
        if j > i
        for t in sorted(vizinhos[i] & vizinhos[j])
        if t > j
    ] if n >= 3 else []
    # Cota barata de S3 (cada trio vale no máximo o seu par menos provável)
    # para não pagar a conta cara dos trios onde ela não vai convergir.
    cota_s3 = 0.0
    for i, j, t in trios:
        cota_s3 += min(juntos[(i, j)], juntos[(i, t)], juntos[(j, t)])
        if n > 3 and cota_s3 > 0.005:
            break
    if n <= 3 or cota_s3 <= 0.005:
        s3 = 0.0
        for i, j, t in trios:
            a, b, c = bilhetes[i], bilhetes[j], bilhetes[t]
            abc = len(a & b & c)
            ab, ac, bc = len(a & b) - abc, len(a & c) - abc, len(b & c) - abc
            tamanhos = (k - ab - ac - abc, k - ab - bc - abc, k - ac - bc - abc, ab, ac, bc, abc)
            s3 += _trio_premia_junto(tamanhos, m, sd, total)
        if n <= 3 or s3 <= 0.0005:
            return min(teto - s2 + s3, teto), "combinatorio"
    return min(qualquer_medido(bilhetes, cfg, rng=rng), teto), "simulado"


def _qualquer_espalhado(
    n_jogos: int, p_uma: float, cfg: dict, rng: random.Random | None = None
) -> tuple[float, str]:
    """Prévia do painel, antes de gerar: chance de levar algo com N bilhetes
    ESPALHADOS pelo gerador do app.

    1. Tabela medida por enumeração exata (`carteira_espalhada`, Lotofácil
       até 20 bilhetes): média de vários lotes, então não depende da sorte de
       um lote só.
    2. Fora dela: monta um lote de prévia com o mesmo motor (semente fixa por
       N, então o painel não muda a cada consulta) e mede com `chance_lote`.
    3. Acima do teto do /generate (200), montar a prévia custaria O(N²) à toa:
       cai no independente, que nunca superestima."""
    tabela = cfg.get("carteira_espalhada") or {}
    if n_jogos in tabela:
        return tabela[n_jogos], "enumerado"
    if n_jogos <= 1:
        return n_jogos * p_uma, "exato"
    if n_jogos > 200:
        return 1 - (1 - p_uma) ** n_jogos, "independente"
    preview_rng = random.Random(90_000 + n_jogos)
    preview = gerar(
        [], "aleatorio", n_jogos, cfg["escolher"], False, loteria=cfg["code"],
        espalhar=True, rng=preview_rng,
    )
    return chance_lote([set(j["dezenas"]) for j in preview], cfg, rng=preview_rng)


def odds_carteira(
    n_jogos: int,
    loteria: str = "mega",
    espalhar: bool = False,
    bilhetes: list[set[int]] | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Probabilidade acumulada de N apostas simples SEPARADAS.

    Para cada faixa, a chance de pelo menos uma das N apostas bater. Como a
    chance marginal é a mesma para qualquer sorteio, apostas distintas se
    comportam como ensaios independentes: P = 1 - (1-p)^N. Vale exatamente
    para o prêmio principal, em que dois bilhetes distintos nunca ganham juntos.

    Para "ganhar algo" a independência é só uma REFERÊNCIA, não um limite: o
    valor real depende de como os bilhetes se sobrepõem, e pode ficar acima
    (espalhados) ou abaixo (bilhetes parecidos, N grande) da fórmula. O teto
    verdadeiro é o da união, min(1, N·p), atingido quando nenhum par pode
    premiar no mesmo sorteio (ver `limiar_sobreposicao`).

    Sem `bilhetes` é a prévia do painel: com `espalhar=True`, o número do que
    o gerador entrega espalhando; sem, o de bilhetes soltos. Com `bilhetes`
    (os jogos de verdade, vindos do /generate), `qualquer` é a chance DESTE
    lote, seja qual for a estratégia: com Atrasados na Lotofácil, por
    exemplo, os jogos repetem as mesmas dezenas e a chance real fica bem
    abaixo da prévia. O retorno médio é o mesmo em todos os casos."""
    cfg = lotteries.get_loteria(loteria)
    base = odds(cfg["escolher"], cfg["preco"], loteria)
    faixas = {}
    for nome, f in base["faixas"].items():
        p = 1 - (1 - f["prob"]) ** n_jogos
        faixas[nome] = {"prob": p, "one_in": _um_em(p)}
    p_uma = sum(f["prob"] for f in base["faixas"].values())
    if bilhetes is not None and n_jogos > 1:
        qualquer, metodo = chance_lote(bilhetes, cfg, rng=rng)
    elif espalhar and n_jogos > 1:
        qualquer, metodo = _qualquer_espalhado(n_jogos, p_uma, cfg, rng=rng)
    else:
        qualquer, metodo = 1 - (1 - p_uma) ** n_jogos, "independente"
    solto = 1 - (1 - p_uma) ** n_jogos
    return {
        "jogos": n_jogos,
        "dezenas": cfg["escolher"],
        "custo_estimado": round(n_jogos * cfg["preco"], 2),
        "espalhar": bool(espalhar and n_jogos > 1),
        "lote": bilhetes is not None,  # True: `qualquer` é a chance dos jogos gerados
        "metodo": metodo,
        "faixas": faixas,
        "qualquer": {
            "prob": qualquer,
            "one_in": round(1 / qualquer, 2) if qualquer else None,
            "pct": round(100 * qualquer, 2),
        },
        # O mesmo dinheiro em bilhetes soltos, para a comparação ficar honesta.
        "qualquer_solto": {
            "prob": solto,
            "one_in": round(1 / solto, 2) if solto else None,
            "pct": round(100 * solto, 2),
        },
    }


def recomendacao(
    draws: list[dict], jogos: int, loteria: str = "mega", teste: dict | None = None
) -> dict:
    """O botão "Qual estratégia usar?": estratégia, Espalhar, custo e chance de
    ganhar algo para `jogos` apostas simples.

    Só a estratégia depende do histórico. Uma estratégia com sinal (Frequência
    ou Atrasados) é recomendada quando o sinal dela se confirmou concurso a
    concurso (z ≥ 1,96, ver stats.sinais_concurso_a_concurso) E o jogo montado
    com ele acertou mais que o acaso; passando as duas, a de sinal mais forte.
    Se nenhuma passa, Aleatório puro: as estratégias empatam e ela é a mais
    simples. Balanceado não tem sinal por dezena para testar. Como o teste roda
    sobre o histórico do banco, a recomendação acompanha cada concurso novo.

    Espalhar, custo e chance são contas fixas (as mesmas de `odds_carteira`).
    `teste` é o resultado do teste já calculado para este histórico, se houver."""
    cfg = lotteries.get_loteria(loteria)
    teste = teste or stats.sinais_concurso_a_concurso(draws, cfg["code"])
    candidatas = [
        (s["z"], nome)
        for nome, s in teste["sinais"].items()
        if s["z"] >= stats.Z_SINAL and s["acertos_jogo"] > s["esperado"]
    ]
    carteira = odds_carteira(jogos, cfg["code"], espalhar=True)
    com, sem = carteira["qualquer"]["prob"], carteira["qualquer_solto"]["prob"]
    return {
        "loteria": cfg["code"],
        "jogos": jogos,
        "estrategia": max(candidatas)[1] if candidatas else "aleatorio",
        **teste,
        "espalhar": {
            "com": com,
            "sem": sem,
            # meio ponto percentual: abaixo disso, na prática tanto faz
            "faz_diferenca": jogos > 1 and com - sem >= 0.005,
        },
        "chance": carteira["qualquer"],
        "custo": round(jogos * cfg["preco"], 2),
        "preco": cfg["preco"],
        "menor_premio": min(cfg["faixas"]),
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
    combos = [tuple(c) for c in combinations(ds, escolher)]
    indice = {c: i for i, c in enumerate(combos)}
    # alvos == candidatos (todos os subconjuntos de tamanho `escolher`).
    # Cobertura de cada candidato como bitmask sobre os índices dos alvos.
    #
    # Em vez de testar o candidato contra TODOS os alvos (O(n²) interseções —
    # 25 milhões numa Mega de 15 dezenas, ~6 s), enumeramos direto os alvos que
    # ele cobre: escolher j dezenas dentro do candidato e escolher-j fora dele.
    # São C(escolher,j)·C(k-escolher,escolher-j) alvos, somados de `garantia`
    # até `escolher` — 55 em vez de 5.005 no mesmo caso. O bitmask final é
    # idêntico, então o fechamento gerado é exatamente o mesmo de antes.
    cov = []
    for ap in combos:
        fora = tuple(n for n in ds if n not in ap)
        mask = 0
        for j in range(garantia, escolher + 1):
            if escolher - j > len(fora):
                continue
            for dentro in combinations(ap, j):
                for extra in combinations(fora, escolher - j):
                    mask |= 1 << indice[tuple(sorted(dentro + extra))]
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
        "jogos": [list(combos[i]) for i in escolhidas],
    }


def _um_em(p: float) -> int | None:
    """Converte probabilidade em "1 em N", truncando como a Caixa publica.

    O valor exato de 13 acertos na Lotofácil é 1 em 691,80. Arredondando dá
    692; a Caixa publica 691, e é com o site dela (e com o bilhete impresso)
    que o usuário compara. A diferença entre as duas convenções é de 0,2% na
    probabilidade — imperceptível —, mas ver um número diferente do oficial
    faz o app parecer errado. Então seguimos a convenção oficial."""
    return int(1 / p) if p else None


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
        faixas[nome] = {"prob": p, "one_in": _um_em(p)}
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
            "one_in": _um_em(premiado),
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
