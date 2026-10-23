import os
import time

from fastapi import APIRouter, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from .. import auth, db, lotteries
from ..csv_utils import parse_draws_csv
from ..fetcher import fetch_espelhos, parse_payload

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


def _exige_sessao(x_session_id: str | None) -> None:
    """Gravar resultado exige login. Sem isso, qualquer um que descobrisse o
    endereço do app poderia mandar um resultado falso — e o upsert o gravaria
    por cima do oficial, estragando a conferência dos jogos."""
    if not auth.validar_sessao(x_session_id):
        raise HTTPException(401, "Entre na sua conta para gravar resultados.")


async def _sincronizar(lot: str, max_batch: int) -> dict:
    """Uma rodada de sincronização do servidor: histórico embutido + espelhos.

    Não consulta a Caixa nem a guidi — as duas recusam o IP do Vercel. O
    resultado mais recente, com data e prêmio do próximo concurso, chega pelo
    navegador do usuário (/import-payloads). Aqui só entram concursos que o
    banco ainda não tem (ou tem sem data): um espelho nunca sobrescreve o
    resultado oficial que o navegador trouxe da Caixa."""
    candidatos = {s["concurso"]: s for s in db.load_bundled_seed(lot)}
    espelho, avisos = await fetch_espelhos(lot)
    for s in espelho:
        candidatos.setdefault(s["concurso"], s)
    if not candidatos:
        raise HTTPException(
            502,
            "Nenhuma fonte do servidor respondeu (espelhos fora do ar e sem histórico "
            f"embutido: {avisos[:2]}). Sincronize logado pelo navegador ou importe um CSV.",
        )

    datados = db.concursos_com_data(lot)
    faltando = [candidatos[n] for n in sorted(candidatos) if n not in datados]
    lote = faltando[:max_batch]
    if lote:
        db.upsert_draws(lote, lot)
    return {
        "source": "seed+espelhos",
        "latest_remote": max(candidatos),
        "added": len(lote),
        "errors": avisos[:5],
        "total_local": db.count_draws(lot),
        "remaining": len(faltando) - len(lote),
        "proximo": _proximo_saneado(lot, db.latest_local(lot)),
    }


@router.post("/sync")
async def sync(
    max_batch: int = Query(200, ge=1, le=1000),
    loteria: str | None = Query(default=None),
):
    """Sincronização incremental do servidor, em lotes: o frontend repete a
    chamada até remaining == 0 (cada lote cabe no tempo da função serverless).
    Aberta sem login: só acrescenta o que falta, vindo de fontes fixas."""
    return await _sincronizar(_loteria(loteria), max_batch)


@router.get("/cron/sync")
async def cron_sync(authorization: str | None = Header(default=None)):
    """Sincronização diária disparada pelo Cron Jobs da Vercel (vercel.json).

    Puxa as loterias dos espelhos em lotes, até acabar o que falta ou o tempo
    apertar (a função tem 60 s). Com a variável CRON_SECRET definida no
    projeto, a Vercel a envia como "Authorization: Bearer <segredo>" e só essa
    chamada passa; sem ela o endpoint fica aberto, o que é seguro pelo mesmo
    motivo do /sync."""
    segredo = os.environ.get("CRON_SECRET")
    if segredo and authorization != f"Bearer {segredo}":
        raise HTTPException(401, "não autorizado")
    inicio = time.monotonic()
    resumo = {}
    for code in lotteries.LOTERIAS:
        adicionados, r = 0, None
        while time.monotonic() - inicio < 45:
            r = await _sincronizar(code, 200)
            adicionados += r["added"]
            if r["remaining"] <= 0 or r["added"] == 0:
                break
        ultimo = db.latest_local(code)
        resumo[code] = {
            "added": adicionados,
            "remaining": r["remaining"] if r else None,
            "ultimo": ultimo["concurso"] if ultimo else None,
            "errors": r["errors"] if r else ["sem tempo para sincronizar"],
        }
    return resumo


class PayloadsImport(BaseModel):
    payloads: list[dict] = Field(min_length=1, max_length=200)


@router.post("/import-payloads")
def import_payloads(
    req: PayloadsImport,
    loteria: str | None = Query(default=None),
    x_session_id: str | None = Header(default=None),
):
    """Recebe payloads brutos (formato Caixa/guidi) buscados PELO NAVEGADOR
    do usuário e grava no banco.

    Por quê: a Caixa/guidi bloqueiam IPs de datacenter (o servidor), mas não
    o IP residencial do usuário. Então o frontend busca os concursos novos
    direto no navegador e repassa para cá — o servidor valida com o mesmo
    parser das fontes oficiais antes de gravar.
    """
    _exige_sessao(x_session_id)
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
async def import_csv(
    file: UploadFile,
    loteria: str | None = Query(default=None),
    x_session_id: str | None = Header(default=None),
):
    """Plano C: importa um CSV com colunas concurso, data, dezena1..dezenaN.

    O parser é o da loteria de destino: um CSV da Mega enviado para a Lotofácil
    (ou o contrário) é recusado em vez de entrar truncado."""
    _exige_sessao(x_session_id)
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
