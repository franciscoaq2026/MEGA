from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from .. import db, lotteries
from ..csv_utils import parse_draws_csv
from ..fetcher import FetchError, fetch_latest, fetch_many, parse_payload

router = APIRouter(tags=["sorteios"])

# Teto do upload de CSV. O histórico completo da Lotofácil (3.657 linhas) tem
# ~180 KB, então 4 MB é folgado — e evita ler um arquivo enorme na memória.
MAX_CSV_BYTES = 4 * 1024 * 1024


def _loteria(code: str | None) -> str:
    return lotteries.get_loteria(code)["code"]


def _prox_key(loteria: str) -> str:
    # Mantém a chave histórica da Mega; demais loterias são namespaced.
    return "proximo" if loteria == "mega" else f"proximo:{loteria}"


def _proximo_saneado(lot: str, ultimo: dict | None) -> dict | None:
    """Evita mostrar um "próximo concurso" defasado. Se o valor guardado
    estiver ausente ou for <= ao último sorteio já no cache (meta antiga que
    não acompanhou os concursos adicionados depois), deriva o próximo do
    último local (nº +1), sem data/prêmio (que seriam do concurso errado)."""
    prox = db.get_meta(_prox_key(lot))
    if not ultimo:
        return prox
    if prox and prox.get("concurso") and prox["concurso"] > ultimo["concurso"]:
        return prox
    return {
        "concurso": ultimo["concurso"] + 1,
        "data": None,
        "estimativa": None,
        "acumulado": None,
    }


@router.get("/status")
def status(loteria: str | None = Query(default=None)):
    lot = _loteria(loteria)
    ultimo = db.latest_local(lot)
    return {
        "loteria": lot,
        "total_draws": db.count_draws(lot),
        "ultimo_local": ultimo,
        "proximo": _proximo_saneado(lot, ultimo),
        "db_backend": db.backend_name(),
    }


@router.get("/draws")
def draws(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    loteria: str | None = Query(default=None),
):
    lot = _loteria(loteria)
    return {
        "total": db.count_draws(lot),
        "items": db.list_draws(limit, offset, lot),
    }


@router.get("/draws/{concurso}")
def draw(concurso: int, loteria: str | None = Query(default=None)):
    lot = _loteria(loteria)
    found = db.get_draw(concurso, lot)
    if not found:
        raise HTTPException(404, f"concurso {concurso} não está no cache local")
    return found


def _sync_from_seed(lot: str, max_batch: int) -> dict:
    """Fallback: carrega o histórico embutido no repositório, em lotes.

    Usado quando as APIs da Caixa/guidi não respondem (ex.: no Vercel, cujo
    IP de datacenter é bloqueado por elas). Os dados já vêm no deploy, então
    aqui é só cópia local do arquivo -> banco, sem rede externa.
    """
    seed = db.load_bundled_seed(lot)
    if not seed:
        raise HTTPException(
            502,
            "APIs de resultados indisponíveis e nenhum histórico embutido encontrado. "
            "Sincronize pelo navegador (IP residencial) ou importe um CSV.",
        )
    existing = db.concursos_com_data(lot)
    missing = [s for s in seed if s["concurso"] not in existing]
    batch = missing[:max_batch]
    if batch:
        db.upsert_draws(batch, lot)

    last = max(s["concurso"] for s in seed)
    ultimo_local = db.latest_local(lot)
    if not ultimo_local or last >= ultimo_local["concurso"]:
        db.set_meta(
            _prox_key(lot),
            {"concurso": last + 1, "data": None, "estimativa": None, "acumulado": None},
        )
    return {
        "source": "dados-embutidos",
        "latest_remote": last,
        "added": len(batch),
        "errors": [],
        "total_local": db.count_draws(lot),
        "remaining": len(missing) - len(batch),
        "proximo": db.get_meta(_prox_key(lot)),
    }


@router.post("/sync")
async def sync(
    max_batch: int = Query(200, ge=1, le=1000),
    loteria: str | None = Query(default=None),
):
    """Sincronização incremental: busca só o que falta, em lotes.

    Tenta a API da Caixa (com fallback guidi) — que funciona a partir de um IP
    residencial. Se ambas falharem (caso do Vercel), cai para o histórico
    embutido no repositório. O frontend chama repetidamente até remaining == 0.
    """
    lot = _loteria(loteria)
    try:
        latest = await fetch_latest(lot)
    except FetchError:
        return _sync_from_seed(lot, max_batch)

    latest_num = latest["concurso"]
    # Só atualiza o "próximo" se a fonte não estiver defasada em relação ao que
    # já temos localmente. Evita que um espelho estático atrasado rebaixe o
    # próximo depois de o navegador já ter trazido concursos mais novos.
    ultimo_local = db.latest_local(lot)
    if not ultimo_local or latest_num >= ultimo_local["concurso"]:
        db.set_meta(_prox_key(lot), latest["proximo"])

    # Precisa buscar: concursos ausentes OU salvos sem data.
    dated = db.concursos_com_data(lot)
    need = [n for n in range(1, latest_num + 1) if n not in dated]
    batch_nums = need[:max_batch]

    # Resolve cada concurso: primeiro do histórico embutido (instantâneo, sem
    # rede), e só o que for mais novo que o seed vem da rede.
    seed = {s["concurso"]: s for s in db.load_bundled_seed(lot)}
    from_seed = [seed[n] for n in batch_nums if n in seed]
    to_fetch = [n for n in batch_nums if n not in seed]

    fetched, errors = ([], [])
    if to_fetch:
        fetched, errors = await fetch_many(to_fetch, lot)
    rows = from_seed + fetched
    if rows:
        db.upsert_draws(rows, lot)

    return {
        "source": "api+seed",
        "latest_remote": latest_num,
        "added": len(rows),
        "errors": errors[:5],
        "total_local": db.count_draws(lot),
        "remaining": len(need) - len(batch_nums),
        "proximo": latest["proximo"],
    }


class PayloadsImport(BaseModel):
    payloads: list[dict] = Field(min_length=1, max_length=200)


@router.post("/import-payloads")
def import_payloads(req: PayloadsImport, loteria: str | None = Query(default=None)):
    """Recebe payloads brutos (formato Caixa/guidi) buscados PELO NAVEGADOR
    do usuário e grava no banco.

    Por quê: a Caixa/guidi bloqueiam IPs de datacenter (o servidor), mas não
    o IP residencial do usuário. Então o frontend busca os concursos novos
    direto no navegador e repassa para cá — o servidor valida com o mesmo
    parser das fontes oficiais antes de gravar.
    """
    lot = _loteria(loteria)
    rows: list[dict] = []
    errors: list[str] = []
    for p in req.payloads:
        try:
            rows.append(parse_payload(p, lot))
        except Exception as e:  # noqa: BLE001 - payload inválido é só pulado
            errors.append(str(e))
    if not rows:
        raise HTTPException(400, f"nenhum payload válido ({errors[:3]})")

    db.upsert_draws(rows, lot)
    newest = max(rows, key=lambda r: r["concurso"])
    ultimo = db.latest_local(lot)
    if newest["proximo"].get("concurso") and ultimo and newest["concurso"] >= ultimo["concurso"]:
        db.set_meta(_prox_key(lot), newest["proximo"])

    return {
        "added": len(rows),
        "skipped": len(errors),
        "errors": errors[:5],
        "total_draws": db.count_draws(lot),
    }


@router.post("/import-csv")
async def import_csv(file: UploadFile, loteria: str | None = Query(default=None)):
    """Plano C: importa um CSV com colunas concurso, data, dezena1..dezenaN.

    O parser é o da loteria de destino: um CSV da Mega enviado para a Lotofácil
    (ou o contrário) é recusado em vez de entrar truncado."""
    lot = _loteria(loteria)
    raw = await file.read()
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(
            413,
            f"arquivo grande demais ({len(raw) // 1024} KB); o limite é "
            f"{MAX_CSV_BYTES // 1024} KB",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    rows, errors = parse_draws_csv(text, lot)
    if not rows:
        raise HTTPException(400, f"nenhuma linha válida no CSV ({errors[:3]})")
    db.upsert_draws(rows, lot)
    return {
        "imported": len(rows),
        "skipped": len(errors),
        "errors": errors[:5],
        "total_draws": db.count_draws(lot),
    }
