from fastapi import APIRouter, HTTPException, Query, UploadFile

from .. import db
from ..csv_utils import parse_draws_csv
from ..fetcher import FetchError, fetch_latest, fetch_many

router = APIRouter(tags=["sorteios"])


@router.get("/status")
def status():
    return {
        "total_draws": db.count_draws(),
        "ultimo_local": db.latest_local(),
        "proximo": db.get_meta("proximo"),
        "db_backend": db.backend_name(),
    }


@router.get("/draws")
def draws(limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)):
    return {
        "total": db.count_draws(),
        "items": db.list_draws(limit, offset),
    }


@router.get("/draws/{concurso}")
def draw(concurso: int):
    found = db.get_draw(concurso)
    if not found:
        raise HTTPException(404, f"concurso {concurso} não está no cache local")
    return found


@router.post("/sync")
async def sync(max_batch: int = Query(300, ge=1, le=1000)):
    """Sincronização incremental: busca só o que falta, em lotes.

    O frontend chama repetidamente até remaining == 0 (mostrando progresso),
    o que também respeita o limite de tempo por requisição em serverless.
    """
    try:
        latest = await fetch_latest()
    except FetchError as e:
        raise HTTPException(502, f"APIs de resultados indisponíveis: {e}") from e

    existing = db.all_concursos()
    latest_is_new = latest["concurso"] not in existing
    db.upsert_draws([latest])
    db.set_meta("proximo", latest["proximo"])

    missing = [n for n in range(1, latest["concurso"]) if n not in existing]
    batch = missing[:max_batch]

    added, errors = ([], [])
    if batch:
        added, errors = await fetch_many(batch)
        if added:
            db.upsert_draws(added)
        if not added and errors:
            raise HTTPException(
                502, f"sincronização travada: {len(errors)} falhas (ex.: {errors[0]})"
            )

    total = db.count_draws()
    return {
        "latest_remote": latest["concurso"],
        "added": len(added) + (1 if latest_is_new else 0),
        "errors": errors[:5],
        "total_local": total,
        "remaining": max(latest["concurso"] - total, 0),
        "proximo": latest["proximo"],
    }


@router.post("/import-csv")
async def import_csv(file: UploadFile):
    """Plano C: importa um CSV com colunas concurso, data, dezena1..dezena6."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    rows, errors = parse_draws_csv(text)
    if not rows:
        raise HTTPException(400, f"nenhuma linha válida no CSV ({errors[:3]})")
    db.upsert_draws(rows)
    return {
        "imported": len(rows),
        "skipped": len(errors),
        "errors": errors[:5],
        "total_draws": db.count_draws(),
    }
