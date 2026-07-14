"""Métricas estatísticas avançadas de um jogo e distribuições históricas.

Reúne os indicadores que os principais sites brasileiros de Mega-Sena usam
para "caracterizar" um jogo: soma, paridade, primos, moldura/miolo do volante,
quadrantes, dezenas consecutivas, repetição do concurso anterior, faixas,
múltiplos de 3 e terminações.

Lembrete honesto: são descrições de padrões, não previsões. Todo jogo tem
exatamente a mesma probabilidade; os padrões só descrevem como os sorteios
costumam se distribuir.
"""

from statistics import mean, pstdev

PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59}
FIBONACCI = {1, 2, 3, 5, 8, 13, 21, 34, 55}

# Volante 6 linhas x 10 colunas: valor v -> linha (v-1)//10, coluna (v-1)%10.
# Moldura = borda (primeira/última linha ou coluna); miolo = o resto.
MOLDURA = {
    v for v in range(1, 61)
    if (v - 1) // 10 in (0, 5) or (v - 1) % 10 in (0, 9)
}


def _quadrante(v: int) -> int:
    """4 quadrantes do volante (linhas 0-2/3-5 x colunas 0-4/5-9)."""
    linha, col = (v - 1) // 10, (v - 1) % 10
    return (0 if linha < 3 else 2) + (0 if col < 5 else 1)


def max_consecutivos(dezenas: list[int]) -> int:
    ds = sorted(dezenas)
    best = run = 1
    for a, b in zip(ds, ds[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    return best


def metrics(dezenas: list[int], anterior: list[int] | None = None) -> dict:
    """Todos os indicadores de um único jogo."""
    ds = sorted(dezenas)
    pares = sum(1 for n in ds if n % 2 == 0)
    quad = [0, 0, 0, 0]
    for n in ds:
        quad[_quadrante(n)] += 1
    return {
        "soma": sum(ds),
        "pares": pares,
        "impares": len(ds) - pares,
        "primos": sum(1 for n in ds if n in PRIMES),
        "fibonacci": sum(1 for n in ds if n in FIBONACCI),
        "multiplos_3": sum(1 for n in ds if n % 3 == 0),
        "moldura": sum(1 for n in ds if n in MOLDURA),
        "miolo": sum(1 for n in ds if n not in MOLDURA),
        "baixas": sum(1 for n in ds if n <= 30),
        "altas": sum(1 for n in ds if n > 30),
        "consecutivos": max_consecutivos(ds),
        "terminacoes_distintas": len({n % 10 for n in ds}),
        "repetidas_anterior": (
            len(set(ds) & set(anterior)) if anterior is not None else None
        ),
    }


# Indicadores numéricos que têm "faixa típica" e entram no termômetro/filtros.
SCALAR_KEYS = (
    "soma",
    "pares",
    "primos",
    "moldura",
    "baixas",
    "consecutivos",
    "multiplos_3",
    "repetidas_anterior",
)

LABELS = {
    "soma": "Soma das dezenas",
    "pares": "Números pares",
    "primos": "Números primos",
    "moldura": "Dezenas na moldura",
    "baixas": "Dezenas baixas (1–30)",
    "consecutivos": "Maior sequência consecutiva",
    "multiplos_3": "Múltiplos de 3",
    "repetidas_anterior": "Repetidas do concurso anterior",
}


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def historical_ranges(draws: list[dict]) -> dict:
    """Distribuições históricas de cada indicador, com faixa típica (p10–p90),
    média e desvio. Usado como default inteligente dos filtros e base do
    termômetro. `draws` em ordem crescente de concurso."""
    series: dict[str, list[int]] = {k: [] for k in SCALAR_KEYS}
    anterior = None
    for d in draws:
        m = metrics(d["dezenas"], anterior)
        for k in SCALAR_KEYS:
            if m[k] is not None:
                series[k].append(m[k])
        anterior = d["dezenas"]

    out = {}
    for k, vals in series.items():
        if not vals:
            continue
        sv = sorted(vals)
        out[k] = {
            "label": LABELS[k],
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


def score(dezenas: list[int], ranges: dict, anterior: list[int] | None = None) -> dict:
    """Termômetro: nota 0–100 de quão 'dentro dos padrões' um jogo está.

    Para cada indicador, dá pontos cheios se cai na faixa típica (p10–p90) e
    desconta proporcionalmente à distância (em desvios-padrão) quando sai. É
    uma medida de tipicidade — não de chance de ganhar."""
    r = ranges.get("ranges", ranges)
    m = metrics(dezenas, anterior)
    criterios = []
    total = 0.0
    usados = 0
    for k in SCALAR_KEYS:
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
