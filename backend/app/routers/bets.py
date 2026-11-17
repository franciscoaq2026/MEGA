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

# manual = escolhido por você; app = gerado aqui; bolao = jogo de um bolão
# (de outra pessoa ou lotérica), fora do comparativo "você vs. app".
ORIGENS = ("manual", "app", "bolao")


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
    # Espalhar no momento da geração: True/False num lote de 2+ bilhetes
    # simples; None quando não se aplica (1 jogo, múltipla, Fábrica, manual)
    # ou em jogos salvos antes de o campo existir.
    espalhar: bool | None = None
    # True quando o valor de `espalhar` veio do estudo de sobreposição feito
    # depois (jogos salvos antes de o campo existir), não da hora de salvar.
    espalhar_deduzido: bool | None = None
    dezenas: list[int]
    criado_em: str | None = None
    # Bolão: os jogos de um mesmo bolão compartilham o nome (único dentro do
    # concurso) e as cotas — quantas são suas e quantas o bolão tem. Só
    # valem para origem "bolao"; nos demais jogos ficam None.
    bolao: str | None = Field(default=None, max_length=60)
    cotas: int | None = Field(default=None, ge=1, le=1000)
    cotas_total: int | None = Field(default=None, ge=1, le=1000)

    @model_validator(mode="after")
    def _valida(self):
        if self.origem not in ORIGENS:
            raise ValueError("origem deve ser 'manual', 'app' ou 'bolao'")
        if self.origem == "bolao":
            self.bolao = (self.bolao or "").strip()
            if not self.bolao:
                raise ValueError("bolão precisa de um nome")
            if self.cotas and self.cotas_total and self.cotas > self.cotas_total:
                raise ValueError("suas cotas não podem passar do total de cotas do bolão")
        else:
            self.bolao = self.cotas = self.cotas_total = None
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
            "espalhar": self.espalhar,
            "espalhar_deduzido": self.espalhar_deduzido if self.espalhar is not None else None,
            "dezenas": self.dezenas,
            "criado_em": self.criado_em or datetime.now(timezone.utc).isoformat(),
            "bolao": self.bolao,
            "cotas": self.cotas,
            "cotas_total": self.cotas_total,
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
