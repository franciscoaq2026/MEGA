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


def _sync_from_seed(max_batch: int) -> dict:
    """Fallback: carrega o histórico embutido no repositório, em lotes.

    Usado quando as APIs da Caixa/guidi não respondem (ex.: no Vercel, cujo
    IP de datacenter é bloqueado por elas). Os dados já vêm no deploy, então
    aqui é só cópia local do arquivo -> banco, sem rede externa.
    """
    seed = db.load_bundled_seed()
    if not seed:
        raise HTTPException(
            502,
            "APIs de resultados indisponíveis e nenhum histórico embutido encontrado. "
            "Use a importação de CSV.",
        )
    existing = db.all_concursos()
    missing = [s for s in seed if s["concurso"] not in existing]
    batch = missing[:max_batch]
    if batch:
        db.upsert_draws(batch)

    last = max(s["concurso"] for s in seed)
    db.set_meta(
        "proximo",
        {"concurso": last + 1, "data": None, "estimativa": None, "acumulado": None},
    )
    return {
        "source": "dados-embutidos",
        "latest_remote": last,
        "added": len(batch),
        "errors": [],
        "total_local": db.count_draws(),
        "remaining": len(missing) - len(batch),
        "proximo": db.get_meta("proximo"),
    }


@router.post("/sync")
async def sync(max_batch: int = Query(200, ge=1, le=1000)):
    """Sincronização incremental: busca só o que falta, em lotes.

    Tenta a API da Caixa (com fallback guidi) — que funciona a partir de um IP
    residencial. Se ambas falharem (caso do Vercel), cai para o histórico
    embutido no repositório. O frontend chama repetidamente até remaining == 0.
    """
    try:
        latest = await fetch_latest()
    except FetchError:
        return _sync_from_seed(max_batch)

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
            # APIs deram latest mas falharam no histórico: usa o embutido.
            return _sync_from_seed(max_batch)

    total = db.count_draws()
    return {
        "source": "api",
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
