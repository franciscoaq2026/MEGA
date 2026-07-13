"""Conferência de apostas contra resultados e backtest de estratégias."""

import random

from . import db, generator

FAIXAS = {6: "sena", 5: "quina", 4: "quadra"}


def conferir(dezenas: list[int], resultado: list[int]) -> dict:
    acertos = len(set(dezenas) & set(resultado))
    return {"acertos": acertos, "faixa": FAIXAS.get(acertos)}


def conferir_apostas(apostas: list[dict]) -> list[dict]:
    """Confere uma lista de {concurso, dezenas} contra o cache local."""
    out = []
    for a in apostas:
        draw = db.get_draw(a["concurso"])
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
            c = conferir(a["dezenas"], draw["dezenas"])
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


def backtest(draws: list[dict], ultimos: int = 100, min_historico: int = 50) -> dict:
    """Simula jogar cada estratégia (1 jogo de 6 dezenas por concurso) nos
    últimos N concursos, usando SOMENTE o histórico anterior a cada sorteio.

    O rng é semeado pelo número do concurso, então o resultado é reprodutível.
    Esperado pelo acaso: 6*6/60 = 0,6 acerto por jogo, para qualquer estratégia.
    """
    if len(draws) < min_historico + 1:
        raise ValueError(
            f"histórico insuficiente para backtest (mínimo {min_historico + 1} concursos)"
        )
    inicio = max(min_historico, len(draws) - ultimos)
    alvo = draws[inicio:]

    resultados = {
        nome: {"acertos_total": 0, "distrib": {i: 0 for i in range(7)}}
        for nome in generator.GERADORES
    }
    for i, alvo_draw in enumerate(alvo, start=inicio):
        prior = draws[:i]
        sorteadas = set(alvo_draw["dezenas"])
        for nome, fn in generator.GERADORES.items():
            rng = random.Random(alvo_draw["concurso"] * 1000 + hash(nome) % 1000)
            jogo = fn(rng, prior, 6)
            acertos = len(set(jogo) & sorteadas)
            resultados[nome]["acertos_total"] += acertos
            resultados[nome]["distrib"][acertos] += 1

    n = len(alvo)
    return {
        "concursos_simulados": n,
        "primeiro_concurso": alvo[0]["concurso"],
        "ultimo_concurso": alvo[-1]["concurso"],
        "esperado_por_jogo": 0.6,
        "estrategias": {
            nome: {
                "media_acertos": round(r["acertos_total"] / n, 3),
                "distrib": r["distrib"],
            }
            for nome, r in resultados.items()
        },
    }
