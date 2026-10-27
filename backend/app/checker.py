"""Conferência de apostas contra resultados e backtest de estratégias."""

import random
from collections import Counter
from math import exp, lgamma, log, log1p, sqrt
from zlib import crc32

from . import db, generator, lotteries

# Janelas do backtest que a tela oferece. Todas terminam no último concurso.
JANELAS = (50, 100, 200)


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


def _faixa_binomial(n: int, p: float, nivel: float = 0.95) -> tuple[int, int]:
    """Do menor ao maior número de concursos premiados que o acaso entrega em
    `nivel` das vezes, para n concursos com chance p cada (corta metade do
    resto em cada ponta)."""
    if p <= 0:
        return 0, 0
    if p >= 1:
        return n, n
    cauda = (1 - nivel) / 2
    acumulado = 0.0
    lo = None
    for k in range(n + 1):
        acumulado += exp(
            lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + k * log(p) + (n - k) * log1p(-p)
        )
        if lo is None and acumulado >= cauda:
            lo = k
        if acumulado >= 1 - cauda:
            return lo, k
    return lo if lo is not None else 0, n


def regua_do_acaso(janela: int, jogos: int, chance: float, esperado: float, desvio: float) -> dict:
    """Quanto o backtest varia SÓ POR SORTE numa janela de `janela` concursos
    com `jogos` apostas em cada: a faixa de concursos com prêmio e a de média
    de acertos por jogo onde caem 95% dos resultados de jogos ao acaso.

    A margem da média trata os jogos do mesmo concurso como independentes.
    Espalhados, eles dividem menos dezenas que dois jogos ao acaso e por isso
    variam um pouco MENOS juntos — a faixa fica do lado folgado, nunca apertada
    demais."""
    lo, hi = _faixa_binomial(janela, chance)
    margem = 1.96 * desvio / sqrt(janela * jogos)
    return {
        "concursos": janela,
        "esperado": round(janela * chance, 2),
        "min": lo,
        "max": hi,
        "media_min": round(esperado - margem, 3),
        "media_max": round(esperado + margem, 3),
    }


def simular(
    draws: list[dict],
    ultimos: int = 100,
    min_historico: int = 50,
    loteria: str = "mega",
    jogos: int = 1,
    espalhar: bool = True,
) -> dict:
    """Joga cada estratégia nos últimos N concursos, com `jogos` apostas
    simples por concurso geradas como o botão Gerar faria (com ou sem o
    Espalhar), usando SOMENTE o histórico anterior a cada sorteio. Guarda os
    acertos de cada jogo; `resumir` transforma isso no resultado da tela.

    O rng é semeado pelo número do concurso e pelo nome da estratégia, então o
    resultado é reprodutível — inclusive entre execuções diferentes. A semente
    usa crc32 do nome, e não `hash()`: o hash de str em Python é aleatorizado a
    cada processo (PYTHONHASHSEED), o que fazia o mesmo backtest devolver
    números distintos a cada reinício do servidor.

    Daí saem duas propriedades que deixam reaproveitar uma simulação:
    - os jogos de um concurso não dependem da janela, então a simulação dos
      últimos 200 contém a dos últimos 100 e a dos últimos 50;
    - o gerador monta os jogos um depois do outro, então os 3 primeiros de um
      lote de 5 são exatamente o lote de 3.
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
    acertos: dict[str, list[list[int]]] = {nome: [] for nome in generator.GERADORES}

    # Resumo do histórico mantido concurso a concurso. Recontar o histórico
    # inteiro para cada estratégia em cada concurso era a maior parte do tempo.
    counts: Counter = Counter()
    ultima_vez: dict[int, int] = {}
    premiadas: set[tuple] = set()

    def entra_no_historico(idx: int, d: dict) -> None:
        counts.update(d["dezenas"])
        for dezena in d["dezenas"]:
            ultima_vez[dezena] = idx
        premiadas.add(tuple(sorted(d["dezenas"])))

    for idx, d in enumerate(draws[:inicio]):
        entra_no_historico(idx, d)
    for i, alvo_draw in enumerate(alvo, start=inicio):
        historico = {
            "counts": counts,
            # mesmo valor de generator._delays_pool(draws[:i], pool)
            "delays": {n: i - 1 - ultima_vez[n] if n in ultima_vez else i for n in pool},
            "premiadas": premiadas,
        }
        prior = draws[:i]
        sorteadas = set(alvo_draw["dezenas"])
        for nome, lista in acertos.items():
            rng = random.Random(_semente(alvo_draw["concurso"], nome))
            lote = generator.gerar(
                prior, nome, jogos, escolher, rng=rng, loteria=cfg["code"],
                espalhar=espalhar, historico=historico,
            )
            lista.append([len(set(j["dezenas"]) & sorteadas) for j in lote])
        entra_no_historico(i, alvo_draw)

    return {
        "loteria": cfg["code"],
        "jogos": jogos,
        "espalhar": espalhar,
        "concursos": [d["concurso"] for d in alvo],
        "datas": [d["data"] for d in alvo],
        "acertos": acertos,
    }


def resumir(sim: dict, ultimos: int | None = None, jogos: int | None = None) -> dict:
    """Resultado do backtest para os últimos `ultimos` concursos da simulação,
    contando só os primeiros `jogos` de cada concurso (ver `simular`).

    Além da média por jogo, conta o que interessa a quem joga alguns bilhetes
    por concurso: em quantos concursos pelo menos um premiou, quantos bilhetes
    caíram em cada faixa e quanto voltou nas faixas de valor fixo. `acaso` traz
    a régua de quanto isso varia só por sorte, nesta janela e nas da tela.

    Esperado pelo acaso = escolher × sorteadas / total, igual para qualquer
    estratégia: 0,6 acerto na Mega (6·6/60) e 9,0 na Lotofácil (15·15/25)."""
    cfg = lotteries.get_loteria(sim["loteria"])
    jogos = sim["jogos"] if jogos is None else jogos
    if jogos > sim["jogos"]:
        raise ValueError(f"a simulação tem {sim['jogos']} jogo(s) por concurso, não {jogos}")
    n = len(sim["concursos"]) if ultimos is None else min(ultimos, len(sim["concursos"]))
    espalhar = sim["espalhar"] and jogos > 1  # com 1 jogo não há o que espalhar
    escolher = cfg["escolher"]
    faixa_minima = min(cfg["faixas"])
    fixos = cfg.get("premios_fixos") or {}
    esperado = round(escolher * cfg["sorteadas"] / cfg["total"], 3)

    estrategias = {}
    for nome, por_concurso in sim["acertos"].items():
        distrib = {i: 0 for i in range(min(escolher, cfg["sorteadas"]) + 1)}
        concursos_com_premio = 0
        for lote in por_concurso[-n:]:
            lote = lote[:jogos]
            for a in lote:
                distrib[a] += 1
            concursos_com_premio += max(lote) >= faixa_minima
        premios = {ac: distrib.get(ac, 0) for ac in sorted(cfg["faixas"])}
        estrategias[nome] = {
            "media_acertos": round(sum(a * q for a, q in distrib.items()) / (n * jogos), 3),
            "distrib": distrib,
            "concursos_com_premio": concursos_com_premio,
            "premios": premios,
            # Só as faixas de valor fixo (Lotofácil 11 a 13). As de rateio
            # mudam a cada concurso e o histórico não guarda quanto pagaram:
            # entram só na contagem de `premios_rateio`.
            "retorno_fixo": (
                round(sum(q * fixos[ac] for ac, q in premios.items() if ac in fixos), 2)
                if fixos
                else None
            ),
            "premios_rateio": sum(q for ac, q in premios.items() if ac not in fixos),
        }

    chance = generator.odds_carteira(jogos, cfg["code"], espalhar=espalhar)["qualquer"]["prob"]
    desvio = generator.distribuicao_acertos(escolher, cfg["code"])["desvio"]
    return {
        "concursos_simulados": n,
        "primeiro_concurso": sim["concursos"][-n],
        "ultimo_concurso": sim["concursos"][-1],
        "primeira_data": sim["datas"][-n],
        "ultima_data": sim["datas"][-1],
        "jogos_por_concurso": jogos,
        "espalhar": espalhar,
        "esperado_por_jogo": esperado,
        "faixa_minima": faixa_minima,
        "gasto": round(n * jogos * cfg["preco"], 2),
        "acaso": {
            # chance de pelo menos um dos `jogos` premiar num concurso, para
            # jogos ao acaso — a mesma conta do painel do gerador
            "chance_por_concurso": chance,
            **regua_do_acaso(n, jogos, chance, esperado, desvio),
            "janelas": [regua_do_acaso(w, jogos, chance, esperado, desvio) for w in JANELAS],
        },
        "estrategias": estrategias,
    }


def backtest(
    draws: list[dict],
    ultimos: int = 100,
    min_historico: int = 50,
    loteria: str = "mega",
    jogos: int = 1,
    espalhar: bool = True,
) -> dict:
    """Simula e resume de uma vez (ver `simular` e `resumir`).

    Com 1 jogo por concurso o resultado é o mesmo de antes de existir o
    parâmetro `jogos`: o gerador fica com o primeiro candidato da estratégia,
    que é o jogo que o backtest sorteava direto."""
    sim = simular(draws, ultimos, min_historico, loteria, jogos, espalhar)
    return resumir(sim)
