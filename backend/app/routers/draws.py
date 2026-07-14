from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from .. import db
from ..csv_utils import parse_draws_csv
from ..fetcher import FetchError, fetch_latest, fetch_many, parse_payload

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
    existing = db.concursos_com_data()
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

    db.set_meta("proximo", latest["proximo"])
    latest_num = latest["concurso"]

    # Precisa buscar: concursos ausentes OU salvos sem data.
    dated = db.concursos_com_data()
    need = [n for n in range(1, latest_num + 1) if n not in dated]
    batch_nums = need[:max_batch]

    # Resolve cada concurso: primeiro do histórico embutido (instantâneo, sem
    # rede), e só o que for mais novo que o seed vem da rede (maickon).
    seed = {s["concurso"]: s for s in db.load_bundled_seed()}
    from_seed = [seed[n] for n in batch_nums if n in seed]
    to_fetch = [n for n in batch_nums if n not in seed]

    fetched, errors = ([], [])
    if to_fetch:
        fetched, errors = await fetch_many(to_fetch)
    rows = from_seed + fetched
    if rows:
        db.upsert_draws(rows)

    return {
        "source": "api+seed",
        "latest_remote": latest_num,
        "added": len(rows),
        "errors": errors[:5],
        "total_local": db.count_draws(),
        "remaining": len(need) - len(batch_nums),
        "proximo": latest["proximo"],
    }


class PayloadsImport(BaseModel):
    payloads: list[dict] = Field(min_length=1, max_length=200)


@router.post("/import-payloads")
def import_payloads(req: PayloadsImport):
    """Recebe payloads brutos (formato Caixa/guidi) buscados PELO NAVEGADOR
    do usuário e grava no banco.

    Por quê: a Caixa/guidi bloqueiam IPs de datacenter (o servidor), mas não
    o IP residencial do usuário. Então o frontend busca os concursos novos
    direto no navegador e repassa para cá — o servidor valida com o mesmo
    parser das fontes oficiais antes de gravar.
    """
    rows: list[dict] = []
    errors: list[str] = []
    for p in req.payloads:
        try:
            rows.append(parse_payload(p))
        except Exception as e:  # noqa: BLE001 - payload inválido é só pulado
            errors.append(str(e))
    if not rows:
        raise HTTPException(400, f"nenhum payload válido ({errors[:3]})")

    db.upsert_draws(rows)
    newest = max(rows, key=lambda r: r["concurso"])
    ultimo = db.latest_local()
    if newest["proximo"].get("concurso") and ultimo and newest["concurso"] >= ultimo["concurso"]:
        db.set_meta("proximo", newest["proximo"])

    return {
        "added": len(rows),
        "skipped": len(errors),
        "errors": errors[:5],
        "total_draws": db.count_draws(),
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
