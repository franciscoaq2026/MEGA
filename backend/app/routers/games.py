from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .. import analysis, checker, db, generator

router = APIRouter(tags=["jogos"])


def _draws_or_409() -> list[dict]:
    draws = db.get_all_draws_asc()
    if not draws:
        raise HTTPException(409, "cache vazio: sincronize os sorteios primeiro")
    return draws


def _valida_dezenas(v: list[int], tamanho_min: int = 1) -> list[int]:
    if len(set(v)) != len(v) or not all(1 <= n <= 60 for n in v):
        raise ValueError("dezenas devem ser únicas e entre 1 e 60")
    return sorted(v)


class GenerateRequest(BaseModel):
    estrategia: Literal["aleatorio", "frequencia", "atrasados", "balanceado"]
    jogos: int = Field(1, ge=1, le=20)
    dezenas: int = Field(6, ge=6, le=20)
    anti_rateio: bool = False


@router.get("/strategies")
def strategies():
    return {"estrategias": generator.ESTRATEGIAS}


@router.post("/generate")
def generate(req: GenerateRequest):
    draws = db.get_all_draws_asc()
    if not draws and req.estrategia != "aleatorio":
        raise HTTPException(
            409,
            "cache vazio: sincronize os sorteios para usar estratégias baseadas no histórico "
            "(o aleatório puro funciona sem histórico)",
        )
    jogos = generator.gerar(draws, req.estrategia, req.jogos, req.dezenas, req.anti_rateio)
    return {
        "estrategia": req.estrategia,
        "descricao": generator.ESTRATEGIAS[req.estrategia],
        "anti_rateio": req.anti_rateio,
        "jogos": jogos,
        "aviso": "Nenhuma estratégia altera a probabilidade real de acerto.",
    }


@router.get("/odds")
def odds(
    dezenas: int = Query(6, ge=6, le=20),
    preco_simples: float = Query(6.0, ge=0, le=1000),
):
    return generator.odds(dezenas, preco_simples)


# ---- Fábrica de números: estatísticas avançadas, gerador, termômetro, fechamento ----


@router.get("/analysis/ranges")
def analysis_ranges():
    """Faixas típicas (p10–p90), média e desvio de cada indicador — base dos
    filtros inteligentes e do termômetro."""
    return analysis.historical_ranges(_draws_or_409())


class Faixa(BaseModel):
    min: int | None = None
    max: int | None = None


class Filtros(BaseModel):
    soma: Faixa | None = None
    pares: Faixa | None = None
    primos: Faixa | None = None
    moldura: Faixa | None = None
    baixas: Faixa | None = None
    repetidas_anterior: Faixa | None = None
    consecutivos_max: int | None = Field(None, ge=1, le=6)

    def to_dict(self) -> dict:
        out: dict = {}
        for k in ("soma", "pares", "primos", "moldura", "baixas", "repetidas_anterior"):
            f = getattr(self, k)
            if f and (f.min is not None or f.max is not None):
                out[k] = [f.min, f.max]
        if self.consecutivos_max is not None:
            out["consecutivos_max"] = self.consecutivos_max
        return out


class GenerateAdvancedRequest(BaseModel):
    jogos: int = Field(3, ge=1, le=50)
    dezenas: int = Field(6, ge=6, le=20)
    filtros: Filtros = Filtros()
    incluir: list[int] = Field(default_factory=list)
    excluir: list[int] = Field(default_factory=list)
    anti_rateio: bool = False

    @field_validator("incluir", "excluir")
    @classmethod
    def _dz(cls, v):
        return _valida_dezenas(v)


@router.post("/generate-advanced")
def generate_advanced(req: GenerateAdvancedRequest):
    draws = _draws_or_409()
    try:
        resultado = generator.gerar_avancado(
            draws,
            jogos=req.jogos,
            dezenas=req.dezenas,
            filtros=req.filtros.to_dict(),
            incluir=req.incluir,
            excluir=req.excluir,
            anti_rateio=req.anti_rateio,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    resultado["aviso"] = "Filtros organizam padrões; não alteram a probabilidade de acerto."
    return resultado


class ScoreRequest(BaseModel):
    dezenas: list[int] = Field(min_length=6, max_length=20)

    @field_validator("dezenas")
    @classmethod
    def _dz(cls, v):
        return _valida_dezenas(v)


@router.post("/score")
def score(req: ScoreRequest):
    draws = _draws_or_409()
    ranges = analysis.historical_ranges(draws)
    anterior = draws[-1]["dezenas"] if draws else None
    resultado = analysis.score(req.dezenas, ranges, anterior)
    resultado["aviso"] = (
        "O termômetro mede o quão típico é o jogo — não a chance de ganhar, "
        "que é idêntica para qualquer combinação."
    )
    return resultado


class WheelRequest(BaseModel):
    dezenas: list[int] = Field(min_length=7, max_length=20)
    tipo: Literal["completa", "reduzida"] = "reduzida"
    garantia: Literal[4, 5] = 4

    @field_validator("dezenas")
    @classmethod
    def _dz(cls, v):
        return _valida_dezenas(v)


@router.post("/wheel")
def wheel(req: WheelRequest):
    k = len(req.dezenas)
    if req.tipo == "completa":
        if k > 11:
            raise HTTPException(
                400,
                f"roda completa de {k} dezenas geraria {generator.comb(k, 6)} jogos; "
                "use até 11 dezenas na completa ou escolha o fechamento reduzido.",
            )
        return generator.roda_completa(req.dezenas)
    if k > 15:
        raise HTTPException(
            400, "fechamento reduzido aceita até 15 dezenas (acima disso fica lento)."
        )
    return generator.fechamento_reduzido(req.dezenas, req.garantia)


class Aposta(BaseModel):
    concurso: int = Field(ge=1)
    dezenas: list[int] = Field(min_length=6, max_length=20)

    @field_validator("dezenas")
    @classmethod
    def dezenas_validas(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v) or not all(1 <= n <= 60 for n in v):
            raise ValueError("dezenas devem ser únicas e estar entre 1 e 60")
        return sorted(v)


class CheckRequest(BaseModel):
    apostas: list[Aposta] = Field(max_length=500)


@router.post("/check")
def check(req: CheckRequest):
    """Confere apostas (guardadas no navegador) contra o cache de resultados."""
    return {"resultados": checker.conferir_apostas([a.model_dump() for a in req.apostas])}


@router.post("/backtest")
def backtest(ultimos: int = Query(100, ge=10, le=500)):
    """Teste honesto: joga cada estratégia nos últimos N concursos usando só
    o histórico anterior de cada um — mostra que nenhuma supera o acaso."""
    draws = db.get_all_draws_asc()
    try:
        return checker.backtest(draws, ultimos)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
