"""Métricas estatísticas avançadas de um jogo e distribuições históricas.

Reúne os indicadores que os sites brasileiros de loteria usam para
"caracterizar" um jogo: soma, paridade, primos, moldura/miolo do volante,
dezenas consecutivas, repetição do concurso anterior, faixas e múltiplos de 3.

Tudo é parametrizado pela loteria (`cfg` de lotteries.py), porque um indicador
que discrimina bem em "6 de 60" pode ser inútil em "15 de 25":

- Na Mega (6 de 60), a *soma* e a *paridade* variam muito entre sorteios.
- Na Lotofácil (15 de 25), quem manda é a *repetição do concurso anterior*
  (média ~9 das 15) e o *miolo* do volante; já "consecutivos" quase não
  discrimina, porque marcar 15 de 25 força sequências longas em todo jogo.

Por isso cada loteria declara seu próprio conjunto de indicadores pontuados
(`SCALAR_KEYS`), em vez de uma lista única.

Lembrete honesto: são descrições de padrões, não previsões. Todo jogo tem
exatamente a mesma probabilidade; os padrões só descrevem como os sorteios
costumam se distribuir.
"""

from statistics import mean, pstdev

from . import lotteries

PRIMES = {
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59,
    61, 67, 71, 73, 79, 83, 89, 97,
}
FIBONACCI = {1, 2, 3, 5, 8, 13, 21, 34, 55, 89}


def _cfg(loteria) -> dict:
    """Aceita o código da loteria ou a própria config."""
    if isinstance(loteria, dict):
        return loteria
    return lotteries.get_loteria(loteria)


def moldura_set(cfg: dict) -> set[int]:
    """Dezenas na borda do volante (primeira/última linha ou coluna).

    Mega: grade 6x10 → 26 dezenas na moldura. Lotofácil: 5x5 → 16."""
    cols = cfg["cols"]
    lin = lotteries.linhas(cfg)
    base = cfg["min_num"]
    out = set()
    for v in lotteries.numbers(cfg):
        linha, col = (v - base) // cols, (v - base) % cols
        if linha in (0, lin - 1) or col in (0, cols - 1):
            out.add(v)
    return out


def corte_baixas(cfg: dict) -> int:
    """Limite das dezenas 'baixas' = metade do intervalo (Mega 30, Lotofácil 13)."""
    return (cfg["min_num"] + cfg["max_num"]) // 2


def max_consecutivos(dezenas: list[int]) -> int:
    ds = sorted(dezenas)
    if not ds:
        return 0
    best = run = 1
    for a, b in zip(ds, ds[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    return best


def metrics(dezenas: list[int], anterior: list[int] | None = None, loteria="mega") -> dict:
    """Todos os indicadores de um único jogo, no contexto da loteria."""
    cfg = _cfg(loteria)
    moldura = moldura_set(cfg)
    corte = corte_baixas(cfg)
    ds = sorted(dezenas)
    pares = sum(1 for n in ds if n % 2 == 0)
    return {
        "soma": sum(ds),
        "pares": pares,
        "impares": len(ds) - pares,
        "primos": sum(1 for n in ds if n in PRIMES),
        "fibonacci": sum(1 for n in ds if n in FIBONACCI),
        "multiplos_3": sum(1 for n in ds if n % 3 == 0),
        "moldura": sum(1 for n in ds if n in moldura),
        "miolo": sum(1 for n in ds if n not in moldura),
        "baixas": sum(1 for n in ds if n <= corte),
        "altas": sum(1 for n in ds if n > corte),
        "consecutivos": max_consecutivos(ds),
        "terminacoes_distintas": len({n % 10 for n in ds}),
        "repetidas_anterior": (
            len(set(ds) & set(anterior)) if anterior is not None else None
        ),
    }


# Indicadores pontuados (termômetro) e filtráveis, POR LOTERIA.
#
# Mega (6 de 60): o conjunto clássico. "consecutivos" discrimina bem, porque
# a maioria dos sorteios não tem nenhuma sequência.
#
# Lotofácil (15 de 25): trocamos "consecutivos" (que é sempre alto — marcar 15
# de 25 força sequências) por "miolo", e mantemos "repetidas_anterior" como
# indicador de peso, já que é o padrão mais estável da modalidade.
SCALAR_KEYS_POR_LOTERIA = {
    "mega": (
        "soma",
        "pares",
        "primos",
        "moldura",
        "baixas",
        "consecutivos",
        "multiplos_3",
        "repetidas_anterior",
    ),
    "lofa": (
        "soma",
        "pares",
        "primos",
        "moldura",
        "miolo",
        "baixas",
        "multiplos_3",
        "repetidas_anterior",
    ),
}

# Fallback para loterias que não declararem um conjunto próprio.
SCALAR_KEYS = SCALAR_KEYS_POR_LOTERIA["mega"]


def scalar_keys(loteria="mega") -> tuple[str, ...]:
    cfg = _cfg(loteria)
    return SCALAR_KEYS_POR_LOTERIA.get(cfg["code"], SCALAR_KEYS)


LABELS = {
    "soma": "Soma das dezenas",
    "pares": "Números pares",
    "primos": "Números primos",
    "moldura": "Dezenas na moldura",
    "miolo": "Dezenas no miolo",
    "baixas": "Dezenas baixas",
    "consecutivos": "Maior sequência consecutiva",
    "multiplos_3": "Múltiplos de 3",
    "repetidas_anterior": "Repetidas do concurso anterior",
}


def label(chave: str, loteria="mega") -> str:
    """Rótulo do indicador, com o intervalo real quando ele depende da loteria."""
    if chave == "baixas":
        cfg = _cfg(loteria)
        return f"Dezenas baixas ({cfg['min_num']}–{corte_baixas(cfg)})"
    return LABELS[chave]


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def historical_ranges(draws: list[dict], loteria="mega") -> dict:
    """Distribuições históricas de cada indicador, com faixa típica (p10–p90),
    média e desvio. Usado como default inteligente dos filtros e base do
    termômetro. `draws` em ordem crescente de concurso."""
    keys = scalar_keys(loteria)
    series: dict[str, list[int]] = {k: [] for k in keys}
    anterior = None
    for d in draws:
        m = metrics(d["dezenas"], anterior, loteria)
        for k in keys:
            if m[k] is not None:
                series[k].append(m[k])
        anterior = d["dezenas"]

    out = {}
    for k, vals in series.items():
        if not vals:
            continue
        sv = sorted(vals)
        out[k] = {
            "label": label(k, loteria),
            "min": sv[0],
            "max": sv[-1],
            "mean": round(mean(vals), 1),
            "std": round(pstdev(vals), 1) if len(vals) > 1 else 0.0,
            "p10": round(_percentile(sv, 0.10)),
            "p90": round(_percentile(sv, 0.90)),
            "p05": round(_percentile(sv, 0.05)),
            "p95": round(_percentile(sv, 0.95)),
        }
    return {"draws_considered": len(draws), "ranges": out}


def score(
    dezenas: list[int],
    ranges: dict,
    anterior: list[int] | None = None,
    loteria="mega",
) -> dict:
    """Termômetro: nota 0–100 de quão 'dentro dos padrões' um jogo está.

    Para cada indicador, dá pontos cheios se cai na faixa típica (p10–p90) e
    desconta proporcionalmente à distância (em desvios-padrão) quando sai. É
    uma medida de tipicidade — não de chance de ganhar."""
    r = ranges.get("ranges", ranges)
    m = metrics(dezenas, anterior, loteria)
    criterios = []
    total = 0.0
    usados = 0
    for k in scalar_keys(loteria):
        if k not in r or m.get(k) is None:
            continue
        info = r[k]
        val = m[k]
        typ_lo, typ_hi = info["p10"], info["p90"]
        std = info["std"] or 1.0
        if typ_lo <= val <= typ_hi:
            pts = 100.0
            situacao = "típico"
        else:
            dist = (typ_lo - val) if val < typ_lo else (val - typ_hi)
            pts = max(0.0, 100.0 - (dist / std) * 35.0)
            situacao = "atípico"
        criterios.append(
            {
                "chave": k,
                "label": info["label"],
                "valor": val,
                "faixa_tipica": [typ_lo, typ_hi],
                "media": info["mean"],
                "situacao": situacao,
                "pontos": round(pts),
            }
        )
        total += pts
        usados += 1
    nota = round(total / usados) if usados else 0
    return {
        "nota": nota,
        "classificacao": _classificar(nota),
        "metrics": m,
        "criterios": criterios,
    }


def _classificar(nota: int) -> str:
    if nota >= 85:
        return "muito dentro do padrão histórico"
    if nota >= 65:
        return "dentro do padrão"
    if nota >= 45:
        return "um pouco fora do padrão"
    return "bem atípico"
