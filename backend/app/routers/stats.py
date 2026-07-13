from fastapi import APIRouter, HTTPException, Query

from .. import db, stats

router = APIRouter(prefix="/stats", tags=["estatísticas"])


def _draws() -> list[dict]:
    draws = db.get_all_draws_asc()
    if not draws:
        raise HTTPException(409, "cache vazio: sincronize os sorteios primeiro")
    return draws


@router.get("/frequency")
def frequency(window: int = Query(0, ge=0, le=10000)):
    return stats.frequency(_draws(), window)


@router.get("/delay")
def delay():
    return stats.current_delays(_draws())


@router.get("/parity")
def parity():
    return stats.parity_distribution(_draws())


@router.get("/sums")
def sums():
    return stats.sum_distribution(_draws())


@router.get("/pairs")
def pairs(limit: int = Query(15, ge=1, le=100)):
    return stats.top_pairs(_draws(), limit)


@router.get("/xray/{concurso}")
def xray(concurso: int):
    try:
        return stats.xray(_draws(), concurso)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
