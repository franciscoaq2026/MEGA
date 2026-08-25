"""Conferência de apostas contra resultados e backtest de estratégias."""

import random
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
    """
    cfg = lotteries.get_loteria(loteria)
    if len(draws) < min_historico + 1:
        raise ValueError(
            f"histórico insuficiente para backtest (mínimo {min_historico + 1} concursos)"
        )
    inicio = max(min_historico, len(draws) - ultimos)
    alvo = draws[inicio:]

    pool = lotteries.numbers(cfg)
    escolher = cfg["escolher"]
    max_acertos = min(escolher, cfg["sorteadas"])
    esperado = round(escolher * cfg["sorteadas"] / cfg["total"], 3)

    resultados = {
        nome: {"acertos_total": 0, "distrib": {i: 0 for i in range(max_acertos + 1)}}
        for nome in generator.GERADORES
    }
    for i, alvo_draw in enumerate(alvo, start=inicio):
        prior = draws[:i]
        sorteadas = set(alvo_draw["dezenas"])
        for nome, fn in generator.GERADORES.items():
            rng = random.Random(_semente(alvo_draw["concurso"], nome))
            jogo = fn(rng, prior, escolher, pool)
            acertos = len(set(jogo) & sorteadas)
            resultados[nome]["acertos_total"] += acertos
            resultados[nome]["distrib"][acertos] += 1

    n = len(alvo)
    return {
        "concursos_simulados": n,
        "primeiro_concurso": alvo[0]["concurso"],
        "ultimo_concurso": alvo[-1]["concurso"],
        "esperado_por_jogo": esperado,
        "estrategias": {
            nome: {
                "media_acertos": round(r["acertos_total"] / n, 3),
                "distrib": r["distrib"],
            }
            for nome, r in resultados.items()
        },
    }
