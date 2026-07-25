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
    cfg = lotteries.get_loteria(loteria)
    if not cfg["avancada"]:
        raise HTTPException(
            409,
            f"{cfg['nome']} ainda não tem análise avançada; use frequência e atraso.",
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
    numbers, drawn = _pool(lot)
    return stats.parity_distribution(_draws(lot), numbers=numbers, drawn=drawn)


@router.get("/sums")
def sums(loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    numbers, drawn = _pool(lot)
    return stats.sum_distribution(_draws(lot), numbers=numbers, drawn=drawn)


@router.get("/pairs")
def pairs(
    limit: int = Query(15, ge=1, le=100),
    loteria: str | None = Query(default=None),
):
    lot = _lot(loteria)
    numbers, drawn = _pool(lot)
    return stats.top_pairs(_draws(lot), limit, numbers=numbers, drawn=drawn)


@router.get("/aleatoriedade")
def aleatoriedade(loteria: str | None = Query(default=None)):
    """Teste de aleatoriedade: qui-quadrado das frequências + distribuição
    observada de cada indicador contra a teórica. É a evidência, com os dados
    do próprio usuário, de que não há padrão a explorar."""
    lot = _lot(loteria)
    draws = _draws(lot)
    try:
        return {
            "chi_square": stats.chi_square_frequencias(draws, lot),
            **stats.indicadores_vs_teoria(draws, lot),
        }
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/xray/{concurso}")
def xray(concurso: int, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    _somente_avancada(lot)
    try:
        return stats.xray(_draws(lot), concurso, lot)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
