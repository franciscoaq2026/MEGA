from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .. import checker, db, generator

router = APIRouter(tags=["jogos"])


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
