from fastapi import APIRouter, HTTPException, Query

from .. import db, lotteries, stats

router = APIRouter(prefix="/stats", tags=["estatísticas"])


def _lot(code: str | None) -> str:
    return lotteries.get_loteria(code)["code"]


def _draws(loteria: str = "mega") -> list[dict]:
    draws = db.get_all_draws_asc(loteria)
    if not draws:
        raise HTTPException(409, "cache vazio: sincronize os sorteios primeiro")
    return draws


def _pool(loteria: str):
    cfg = lotteries.get_loteria(loteria)
    return list(range(cfg["min_num"], cfg["max_num"] + 1)), cfg["sorteadas"]


def _somente_avancada(loteria: str) -> None:
    if not lotteries.get_loteria(loteria)["avancada"]:
        raise HTTPException(
            409,
            "esta análise ainda é específica da Mega-Sena; para esta loteria use "
            "frequência e atraso.",
        )


@router.get("/frequency")
def frequency(
    window: int = Query(0, ge=0, le=10000),
    loteria: str | None = Query(default=None),
):
    lot = _lot(loteria)
    numbers, pick = _pool(lot)
    return stats.frequency(_draws(lot), window, numbers=numbers, pick=pick)


@router.get("/delay")
def delay(loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    numbers, _ = _pool(lot)
    return stats.current_delays(_draws(lot), numbers=numbers)


@router.get("/parity")
def parity(loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    _somente_avancada(lot)
    return stats.parity_distribution(_draws(lot))


@router.get("/sums")
def sums(loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    _somente_avancada(lot)
    return stats.sum_distribution(_draws(lot))


@router.get("/pairs")
def pairs(
    limit: int = Query(15, ge=1, le=100),
    loteria: str | None = Query(default=None),
):
    lot = _lot(loteria)
    _somente_avancada(lot)
    return stats.top_pairs(_draws(lot), limit)


@router.get("/xray/{concurso}")
def xray(concurso: int, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    _somente_avancada(lot)
    try:
        return stats.xray(_draws(lot), concurso)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
