"""Apostas sincronizadas na nuvem (Turso), por conta e loteria.

Autenticação por header X-Session-Id. Sem sessão válida, retorna 401 — o
frontend continua usando o localStorage quando o usuário não está logado.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from .. import auth, db, lotteries

router = APIRouter(prefix="/bets", tags=["bets"])


def _conta(x_session_id: str | None) -> str:
    sessao = auth.validar_sessao(x_session_id)
    if not sessao:
        raise HTTPException(401, "Sessão inválida ou expirada. Faça login novamente.")
    return sessao["account_id"]


class BetIn(BaseModel):
    id: str | None = None
    loteria: str = "mega"
    concurso: int = Field(ge=1)
    origem: str
    estrategia: str | None = None
    dezenas: list[int]
    criado_em: str | None = None

    @model_validator(mode="after")
    def _valida(self):
        if self.origem not in ("manual", "app"):
            raise ValueError("origem deve ser 'manual' ou 'app'")
        cfg = lotteries.get_loteria(self.loteria)
        self.loteria = cfg["code"]
        dz = self.dezenas
        if len(set(dz)) != len(dz):
            raise ValueError("dezenas não podem repetir")
        if not all(cfg["min_num"] <= n <= cfg["max_num"] for n in dz):
            raise ValueError(
                f"dezenas de {cfg['nome']} devem estar entre {cfg['min_num']} e {cfg['max_num']}"
            )
        if not (cfg["escolher"] <= len(dz) <= cfg["max_escolher"]):
            faixa = (
                f"{cfg['escolher']}"
                if cfg["escolher"] == cfg["max_escolher"]
                else f"{cfg['escolher']} a {cfg['max_escolher']}"
            )
            raise ValueError(f"{cfg['nome']} aceita {faixa} dezenas por aposta")
        self.dezenas = sorted(dz)
        return self

    def to_record(self) -> dict:
        return {
            "id": self.id or uuid.uuid4().hex,
            "loteria": self.loteria,
            "concurso": self.concurso,
            "origem": self.origem,
            "estrategia": self.estrategia,
            "dezenas": self.dezenas,
            "criado_em": self.criado_em or datetime.now(timezone.utc).isoformat(),
        }


class SyncRequest(BaseModel):
    bets: list[BetIn] = Field(default_factory=list, max_length=2000)


@router.get("")
def listar(
    loteria: str | None = Query(default=None),
    x_session_id: str | None = Header(default=None),
):
    conta = _conta(x_session_id)
    return {"bets": db.list_bets(conta, loteria)}


@router.post("")
def adicionar(body: BetIn, x_session_id: str | None = Header(default=None)):
    conta = _conta(x_session_id)
    rec = body.to_record()
    db.upsert_bet(conta, rec)
    return {"status": "success", "bet": rec}


@router.delete("/{bet_id}")
def remover(bet_id: str, x_session_id: str | None = Header(default=None)):
    conta = _conta(x_session_id)
    db.delete_bet(conta, bet_id)
    return {"status": "success"}


@router.post("/sync")
def sync(
    body: SyncRequest,
    loteria: str | None = Query(default=None),
    x_session_id: str | None = Header(default=None),
):
    """Migração/merge: envia as apostas locais (união por id no servidor) e
    devolve a lista completa da conta. Se `loteria` for informada, a resposta
    traz só as daquela loteria (mas o upsert grava todas as enviadas)."""
    conta = _conta(x_session_id)
    recs = [b.to_record() for b in body.bets]
    if recs:
        db.upsert_bets(conta, recs)
    return {"bets": db.list_bets(conta, loteria)}
