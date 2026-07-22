"""Apostas sincronizadas na nuvem (Turso), por conta.

Autenticação por header X-Session-Id. Sem sessão válida, retorna 401 — o
frontend continua usando o localStorage quando o usuário não está logado.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import auth, db

router = APIRouter(prefix="/bets", tags=["bets"])


def _conta(x_session_id: str | None) -> str:
    sessao = auth.validar_sessao(x_session_id)
    if not sessao:
        raise HTTPException(401, "Sessão inválida ou expirada. Faça login novamente.")
    return sessao["account_id"]


class BetIn(BaseModel):
    id: str | None = None
    concurso: int = Field(ge=1)
    origem: str
    estrategia: str | None = None
    dezenas: list[int] = Field(min_length=6, max_length=20)
    criado_em: str | None = None

    @field_validator("origem")
    @classmethod
    def _origem(cls, v: str) -> str:
        if v not in ("manual", "app"):
            raise ValueError("origem deve ser 'manual' ou 'app'")
        return v

    @field_validator("dezenas")
    @classmethod
    def _dezenas(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v) or not all(1 <= n <= 60 for n in v):
            raise ValueError("dezenas devem ser únicas e entre 1 e 60")
        return sorted(v)

    def to_record(self) -> dict:
        return {
            "id": self.id or uuid.uuid4().hex,
            "concurso": self.concurso,
            "origem": self.origem,
            "estrategia": self.estrategia,
            "dezenas": self.dezenas,
            "criado_em": self.criado_em or datetime.now(timezone.utc).isoformat(),
        }


class SyncRequest(BaseModel):
    bets: list[BetIn] = Field(default_factory=list, max_length=1000)


@router.get("")
def listar(x_session_id: str | None = Header(default=None)):
    conta = _conta(x_session_id)
    return {"bets": db.list_bets(conta)}


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
def sync(body: SyncRequest, x_session_id: str | None = Header(default=None)):
    """Migração/merge: envia as apostas locais (união por id no servidor) e
    devolve a lista completa da conta — usado no primeiro login."""
    conta = _conta(x_session_id)
    recs = [b.to_record() for b in body.bets]
    if recs:
        db.upsert_bets(conta, recs)
    return {"bets": db.list_bets(conta)}
