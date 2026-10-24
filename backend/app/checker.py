"""Conferência de apostas contra resultados e backtest de estratégias."""

import random
from collections import Counter
from math import sqrt
from zlib import crc32

from . import db, generator, lotteries


def conferir(dezenas: list[int], resultado: list[int], loteria: str = "mega") -> dict:
    """Conta acertos e determina a faixa premiada conforme a loteria.

    Cada loteria tem sua própria tabela de faixas (a Mega premia 6/5/4; a
    Lotofácil, 15/14/13/12/11), por isso consultamos a config em vez de
    aplicar um mínimo fixo.

    Junto vem `avaliacao`: onde esse número de acertos cai na distribuição do
    acaso. Sem essa régua não há como julgar o próprio resultado — 9 acertos
    na Lotofácil soa alto e é exatamente a média de qualquer jogo."""
    faixas = lotteries.get_loteria(loteria)["faixas"]
    acertos = len(set(dezenas) & set(resultado))
    return {
        "acertos": acertos,
        "faixa": faixas.get(acertos),
        "avaliacao": generator.avaliar_acertos(acertos, len(dezenas), loteria),
    }


def conferir_apostas(apostas: list[dict], loteria: str = "mega") -> list[dict]:
    """Confere uma lista de {concurso, dezenas} contra o cache local."""
    out = []
    for a in apostas:
        draw = db.get_draw(a["concurso"], loteria)
        if draw is None:
            out.append(
                {
                    "concurso": a["concurso"],
                    "encontrado": False,
                    "resultado": None,
                    "acertos": None,
                    "faixa": None,
                }
            )
        else:
            c = conferir(a["dezenas"], draw["dezenas"], loteria)
            out.append(
                {
                    "concurso": a["concurso"],
                    "encontrado": True,
                    "resultado": draw["dezenas"],
                    "data": draw["data"],
                    **c,
                }
            )
    return out


def _semente(concurso: int, estrategia: str) -> int:
    """Semente estável do backtest: mesma entrada, mesmo número, sempre."""
    return concurso * 1000 + crc32(estrategia.encode("utf-8")) % 1000


def backtest(
    draws: list[dict], ultimos: int = 100, min_historico: int = 50, loteria: str = "mega"
) -> dict:
    """Simula jogar cada estratégia (1 aposta simples por concurso) nos
    últimos N concursos, usando SOMENTE o histórico anterior a cada sorteio.

    O rng é semeado pelo número do concurso e pelo nome da estratégia, então o
    resultado é reprodutível — inclusive entre execuções diferentes. A semente
    usa crc32 do nome, e não `hash()`: o hash de str em Python é aleatorizado a
    cada processo (PYTHONHASHSEED), o que fazia o mesmo backtest devolver
    números distintos a cada reinício do servidor.

    Esperado pelo acaso = escolher × sorteadas / total, igual para qualquer
    estratégia: 0,6 acerto na Mega (6·6/60) e 9,0 na Lotofácil (15·15/25).

    Junto vem a régua para ler o resultado: `margem_95` é quanto a média de
    uma estratégia SEM poder nenhum oscila por puro acaso em n concursos
    (1,96 desvios-padrão da média hipergeométrica), e `z` diz a quantos
    desvios cada estratégia ficou do esperado. Sem isso, 100 concursos da Mega
    (±0,14 em torno de 0,6) pareciam "estratégia boa" ou "ruim" à toa.

    `ultimos=0` simula o histórico inteiro. Frequência e atraso são mantidos
    incrementalmente — recontar o passado a cada concurso tornava isso
    quadrático e inviável numa função serverless.
    """
    cfg = lotteries.get_loteria(loteria)
    if len(draws) < min_historico + 1:
        raise ValueError(
            f"histórico insuficiente para backtest (mínimo {min_historico + 1} concursos)"
        )
    inicio = min_historico if ultimos <= 0 else max(min_historico, len(draws) - ultimos)
    alvo = draws[inicio:]

    pool = lotteries.numbers(cfg)
    escolher, k, total = cfg["escolher"], cfg["sorteadas"], cfg["total"]
    max_acertos = min(escolher, k)
    esperado = escolher * k / total
    # desvio-padrão dos acertos de UM jogo (hipergeométrica)
    dp_jogo = sqrt(escolher * k * (total - escolher) * (total - k) / (total * total * (total - 1)))

    resultados = {
        nome: {"acertos_total": 0, "distrib": {i: 0 for i in range(max_acertos + 1)}}
        for nome in generator.GERADORES
    }
    counts: Counter = Counter()
    last_seen: dict[int, int] = {}
    for j, d in enumerate(draws[:inicio]):
        counts.update(d["dezenas"])
        for x in d["dezenas"]:
            last_seen[x] = j
    for i, alvo_draw in enumerate(alvo, start=inicio):
        prior = draws[:i]
        # mesmo resultado de generator._delays_pool(prior, pool), sem recontar
        delays = {x: (i - 1 - last_seen[x]) if x in last_seen else i for x in pool}
        resumo = {"frequencia": {"counts": counts}, "atrasados": {"delays": delays},
                  "balanceado": {"counts": counts}}
        sorteadas = set(alvo_draw["dezenas"])
        for nome, fn in generator.GERADORES.items():
            rng = random.Random(_semente(alvo_draw["concurso"], nome))
            jogo = fn(rng, prior, escolher, pool, **resumo.get(nome, {}))
            acertos = len(set(jogo) & sorteadas)
            resultados[nome]["acertos_total"] += acertos
            resultados[nome]["distrib"][acertos] += 1
        counts.update(alvo_draw["dezenas"])
        for x in alvo_draw["dezenas"]:
            last_seen[x] = i

    n = len(alvo)
    dp_media = dp_jogo / sqrt(n)
    return {
        "concursos_simulados": n,
        "primeiro_concurso": alvo[0]["concurso"],
        "ultimo_concurso": alvo[-1]["concurso"],
        "esperado_por_jogo": round(esperado, 3),
        "margem_95": round(1.96 * dp_media, 3),
        "estrategias": {
            nome: {
                "media_acertos": round(r["acertos_total"] / n, 3),
                "z": round((r["acertos_total"] / n - esperado) / dp_media, 2),
                "distrib": r["distrib"],
            }
            for nome, r in resultados.items()
        },
    }
