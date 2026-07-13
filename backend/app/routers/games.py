from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db, generator

router = APIRouter(tags=["jogos"])


class GenerateRequest(BaseModel):
    estrategia: Literal["aleatorio", "frequencia", "atrasados", "balanceado"]
    jogos: int = Field(1, ge=1, le=20)
    dezenas: int = Field(6, ge=6, le=15)
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
    dezenas: int = Query(6, ge=6, le=15),
    preco_simples: float = Query(6.0, ge=0, le=1000),
):
    return generator.odds(dezenas, preco_simples)
