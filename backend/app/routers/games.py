from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import analysis, checker, db, generator, lotteries

router = APIRouter(tags=["jogos"])


def _lot(code: str | None) -> str:
    return lotteries.get_loteria(code)["code"]


def _somente_avancada(loteria: str) -> dict:
    cfg = lotteries.get_loteria(loteria)
    if not cfg["avancada"]:
        raise HTTPException(
            409, f"{cfg['nome']} ainda não tem análise avançada (Fábrica)."
        )
    return cfg


def _draws_or_409(loteria: str = "mega") -> list[dict]:
    draws = db.get_all_draws_asc(loteria)
    if not draws:
        raise HTTPException(409, "cache vazio: sincronize os sorteios primeiro")
    return draws


def _valida_dezenas(v: list[int], cfg: dict) -> list[int]:
    """Dezenas únicas e dentro do volante da loteria (Mega 1–60, Lotofácil 1–25)."""
    lo, hi = cfg["min_num"], cfg["max_num"]
    if len(set(v)) != len(v) or not all(lo <= n <= hi for n in v):
        raise HTTPException(
            400, f"dezenas devem ser únicas e entre {lo} e {hi} ({cfg['nome']})"
        )
    return sorted(v)


def _valida_tamanho(k: int, cfg: dict, minimo: int | None = None) -> int:
    """Tamanho da aposta dentro do que a Caixa aceita para a loteria."""
    lo = cfg["escolher"] if minimo is None else minimo
    hi = cfg["max_escolher"]
    if not lo <= k <= hi:
        raise HTTPException(
            400, f"{cfg['nome']} aceita de {lo} a {hi} dezenas por aposta (recebido: {k})"
        )
    return k


class GenerateRequest(BaseModel):
    estrategia: Literal["aleatorio", "frequencia", "atrasados", "balanceado"]
    jogos: int = Field(1, ge=1, le=20)
    dezenas: int = Field(0, ge=0, le=50)  # 0 = aposta simples da loteria
    anti_rateio: bool = False


@router.get("/strategies")
def strategies():
    return {"estrategias": generator.ESTRATEGIAS}


@router.get("/config")
def config(loteria: str | None = Query(default=None)):
    """Config da loteria que o frontend precisa para montar volante e limites."""
    cfg = lotteries.get_loteria(_lot(loteria))
    return {
        "code": cfg["code"],
        "nome": cfg["nome"],
        "min_num": cfg["min_num"],
        "max_num": cfg["max_num"],
        "escolher": cfg["escolher"],
        "max_escolher": cfg["max_escolher"],
        "sorteadas": cfg["sorteadas"],
        "cols": cfg["cols"],
        "preco": cfg["preco"],
        "avancada": cfg["avancada"],
        "faixas": cfg["faixas"],
        "max_roda_completa": cfg["max_roda_completa"],
        "max_reduzida": cfg["max_reduzida"],
        "garantias": [g for g in sorted(cfg["faixas"]) if g < cfg["escolher"]],
    }


@router.post("/generate")
def generate(req: GenerateRequest, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    cfg = lotteries.get_loteria(lot)
    dezenas = cfg["escolher"] if not req.dezenas else _valida_tamanho(req.dezenas, cfg)
    draws = db.get_all_draws_asc(lot)
    if not draws and req.estrategia != "aleatorio":
        raise HTTPException(
            409,
            "cache vazio: sincronize os sorteios para usar estratégias baseadas no histórico "
            "(o aleatório puro funciona sem histórico)",
        )
    jogos = generator.gerar(draws, req.estrategia, req.jogos, dezenas, req.anti_rateio, loteria=lot)
    return {
        "estrategia": req.estrategia,
        "descricao": generator.ESTRATEGIAS[req.estrategia],
        "anti_rateio": req.anti_rateio,
        "dezenas": dezenas,
        "jogos": jogos,
        "aviso": "Nenhuma estratégia altera a probabilidade real de acerto.",
    }


@router.get("/odds")
def odds(
    dezenas: int = Query(0, ge=0, le=50),
    preco_simples: float | None = Query(None, ge=0, le=1000),
    loteria: str | None = Query(default=None),
):
    """Probabilidade real por faixa e custo de uma aposta de N dezenas.

    Este é o único número do app que muda de verdade com a escolha do usuário:
    mais dezenas = mais combinações cobertas = mais chance, proporcional ao custo.
    """
    lot = _lot(loteria)
    cfg = lotteries.get_loteria(lot)
    k = cfg["escolher"] if not dezenas else _valida_tamanho(dezenas, cfg)
    return generator.odds(k, preco_simples, lot)


# ---- Fábrica de números: estatísticas avançadas, gerador, termômetro, fechamento ----


@router.get("/analysis/ranges")
def analysis_ranges(loteria: str | None = Query(default=None)):
    """Faixas típicas (p10–p90), média e desvio de cada indicador — base dos
    filtros inteligentes e do termômetro."""
    lot = _lot(loteria)
    _somente_avancada(lot)
    return analysis.historical_ranges(_draws_or_409(lot), lot)


class Faixa(BaseModel):
    min: int | None = None
    max: int | None = None


class Filtros(BaseModel):
    soma: Faixa | None = None
    pares: Faixa | None = None
    primos: Faixa | None = None
    moldura: Faixa | None = None
    miolo: Faixa | None = None
    baixas: Faixa | None = None
    multiplos_3: Faixa | None = None
    repetidas_anterior: Faixa | None = None
    consecutivos_max: int | None = Field(None, ge=1, le=20)

    def to_dict(self) -> dict:
        out: dict = {}
        for k in (
            "soma", "pares", "primos", "moldura", "miolo",
            "baixas", "multiplos_3", "repetidas_anterior",
        ):
            f = getattr(self, k)
            if f and (f.min is not None or f.max is not None):
                out[k] = [f.min, f.max]
        if self.consecutivos_max is not None:
            out["consecutivos_max"] = self.consecutivos_max
        return out


class GenerateAdvancedRequest(BaseModel):
    jogos: int = Field(3, ge=1, le=50)
    dezenas: int = Field(0, ge=0, le=50)
    filtros: Filtros = Filtros()
    incluir: list[int] = Field(default_factory=list)
    excluir: list[int] = Field(default_factory=list)
    anti_rateio: bool = False


@router.post("/generate-advanced")
def generate_advanced(req: GenerateAdvancedRequest, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    cfg = _somente_avancada(lot)
    k = cfg["escolher"] if not req.dezenas else _valida_tamanho(req.dezenas, cfg)
    incluir = _valida_dezenas(req.incluir, cfg)
    excluir = _valida_dezenas(req.excluir, cfg)
    draws = _draws_or_409(lot)
    try:
        resultado = generator.gerar_avancado(
            draws,
            jogos=req.jogos,
            dezenas=k,
            filtros=req.filtros.to_dict(),
            incluir=incluir,
            excluir=excluir,
            anti_rateio=req.anti_rateio,
            loteria=lot,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    resultado["aviso"] = "Filtros organizam padrões; não alteram a probabilidade de acerto."
    return resultado


class ScoreRequest(BaseModel):
    dezenas: list[int] = Field(min_length=1, max_length=50)


@router.post("/score")
def score(req: ScoreRequest, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    cfg = _somente_avancada(lot)
    ds = _valida_dezenas(req.dezenas, cfg)
    _valida_tamanho(len(ds), cfg)
    draws = _draws_or_409(lot)
    ranges = analysis.historical_ranges(draws, lot)
    anterior = draws[-1]["dezenas"] if draws else None
    resultado = analysis.score(ds, ranges, anterior, lot)
    resultado["aviso"] = (
        "O termômetro mede o quão típico é o jogo — não a chance de ganhar, "
        "que é idêntica para qualquer combinação."
    )
    return resultado


class WheelRequest(BaseModel):
    dezenas: list[int] = Field(min_length=2, max_length=50)
    tipo: Literal["completa", "reduzida"] = "reduzida"
    garantia: int | None = None


@router.post("/wheel")
def wheel(req: WheelRequest, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    cfg = _somente_avancada(lot)
    ds = _valida_dezenas(req.dezenas, cfg)
    k = len(ds)
    escolher = cfg["escolher"]
    if k <= escolher:
        raise HTTPException(
            400,
            f"o fechamento só faz sentido com MAIS de {escolher} dezenas "
            f"(a aposta simples da {cfg['nome']}); recebido: {k}",
        )

    if req.tipo == "completa":
        if k > cfg["max_roda_completa"]:
            raise HTTPException(
                400,
                f"roda completa de {k} dezenas geraria {generator.comb(k, escolher)} jogos; "
                f"use até {cfg['max_roda_completa']} dezenas na completa ou escolha o "
                "fechamento reduzido.",
            )
        return generator.roda_completa(ds, lot)

    if k > cfg["max_reduzida"]:
        raise HTTPException(
            400,
            f"fechamento reduzido aceita até {cfg['max_reduzida']} dezenas na "
            f"{cfg['nome']} (acima disso fica lento).",
        )
    garantias = [g for g in sorted(cfg["faixas"]) if g < escolher]
    garantia = req.garantia if req.garantia is not None else garantias[-1]
    if garantia not in garantias:
        raise HTTPException(
            400, f"garantia deve ser uma destas faixas da {cfg['nome']}: {garantias}"
        )
    return generator.fechamento_reduzido(ds, garantia, lot)


class Aposta(BaseModel):
    # Intervalo permissivo para cobrir todas as loterias; a conferência é só
    # interseção, então dezenas fora do volante simplesmente não pontuam.
    concurso: int = Field(ge=1)
    dezenas: list[int] = Field(min_length=1, max_length=50)


class CheckRequest(BaseModel):
    apostas: list[Aposta] = Field(max_length=500)


@router.post("/check")
def check(req: CheckRequest, loteria: str | None = Query(default=None)):
    """Confere apostas (guardadas no navegador) contra o cache de resultados."""
    lot = _lot(loteria)
    return {"resultados": checker.conferir_apostas([a.model_dump() for a in req.apostas], lot)}


@router.post("/backtest")
def backtest(
    ultimos: int = Query(100, ge=10, le=500),
    loteria: str | None = Query(default=None),
):
    """Teste honesto: joga cada estratégia nos últimos N concursos usando só
    o histórico anterior de cada um — mostra que nenhuma supera o acaso."""
    lot = _lot(loteria)
    _somente_avancada(lot)
    draws = db.get_all_draws_asc(lot)
    try:
        return checker.backtest(draws, ultimos, loteria=lot)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
