"""Busca de resultados nas APIs públicas.

Fonte principal: API da Caixa (a mesma usada pelo site oficial de loterias).
Fallback: api.guidi.dev.br, que espelha o mesmo formato de payload.
"""

import asyncio
from datetime import datetime

import httpx

from . import lotteries

CAIXA_API = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
GUIDI_API = "https://api.guidi.dev.br/loteria"
# Espelho estático no GitHub (formato idêntico ao da Caixa), atualizado por um
# robô/cron. É a única fonte que funciona a partir de um datacenter (Vercel),
# já que a Caixa e a guidi bloqueiam IPs que não sejam residenciais.
# Só a Mega tem esse espelho; para as demais loterias, só Caixa/guidi.
MAICKON_BASES = {
    "megasena": "https://raw.githubusercontent.com/maickon/free-apiloterias/master/database/megasena",
}

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (loterias-stats; uso pessoal)",
}
TIMEOUT = httpx.Timeout(12.0)


class FetchError(Exception):
    pass


def _to_iso(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_payload(data: dict, loteria: str = "mega") -> dict:
    """Normaliza o payload da Caixa/guidi para o formato interno, validando
    a quantidade e o intervalo de dezenas conforme a loteria."""
    cfg = lotteries.get_loteria(loteria)
    numero = data.get("numero") or data.get("concurso")
    dezenas_raw = (
        data.get("listaDezenas")
        or data.get("dezenas")
        or data.get("dezenasSorteadasOrdemSorteio")
    )
    data_apuracao = _to_iso(data.get("dataApuracao") or data.get("data"))
    if not numero or not dezenas_raw or not data_apuracao:
        raise FetchError(f"payload inesperado: campos ausentes ({list(data)[:8]}...)")
    dezenas = sorted(int(d) for d in dezenas_raw)
    if len(set(dezenas)) != cfg["sorteadas"] or not all(
        cfg["min_num"] <= d <= cfg["max_num"] for d in dezenas
    ):
        raise FetchError(f"dezenas inválidas no payload de {cfg['nome']}: {dezenas_raw}")
    return {
        "concurso": int(numero),
        "data": data_apuracao,
        "dezenas": dezenas,
        "proximo": {
            "concurso": data.get("numeroConcursoProximo"),
            "data": _to_iso(data.get("dataProximoConcurso")),
            "estimativa": data.get("valorEstimadoProximoConcurso"),
            "acumulado": data.get("acumulado"),
        },
    }


class Fetcher:
    """Cliente com fallback: se a Caixa falhar, passa a usar a guidi
    nas próximas chamadas da mesma sessão de sincronização."""

    def __init__(self, client: httpx.AsyncClient, loteria: str = "mega"):
        self.client = client
        self.caixa_ok = True
        self.loteria = lotteries.get_loteria(loteria)["code"]
        self.fonte = lotteries.get_loteria(loteria)["fonte"]

    def _urls(self, concurso: int | None) -> list[str]:
        caixa_base = f"{CAIXA_API}/{self.fonte}"
        guidi_base = f"{GUIDI_API}/{self.fonte}"
        caixa = f"{caixa_base}/{concurso}" if concurso else caixa_base
        guidi = f"{guidi_base}/{concurso}" if concurso else f"{guidi_base}/ultimo"
        # Caixa/guidi primeiro (mais frescos, funcionam em IP residencial);
        # o espelho do GitHub por último, como rede de segurança do Vercel.
        base = [caixa, guidi] if self.caixa_ok else [guidi, caixa]
        maickon_base = MAICKON_BASES.get(self.fonte)
        if maickon_base:
            m = f"{maickon_base}/{concurso}.json" if concurso else f"{maickon_base}/_ultimo.json"
            base.append(m)
        return base

    async def fetch(self, concurso: int | None = None) -> dict:
        last_error: Exception | None = None
        caixa_prefix = f"{CAIXA_API}/{self.fonte}"
        for url in self._urls(concurso):
            try:
                resp = await self.client.get(url, headers=HEADERS, timeout=TIMEOUT)
                resp.raise_for_status()
                return parse_payload(resp.json(), self.loteria)
            except Exception as e:  # noqa: BLE001 - qualquer falha aciona o fallback
                if url.startswith(caixa_prefix):
                    self.caixa_ok = False
                last_error = e
        raise FetchError(
            f"concurso {concurso or 'último'}: nenhuma API respondeu ({last_error})"
        )


async def fetch_latest(loteria: str = "mega") -> dict:
    async with httpx.AsyncClient() as client:
        return await Fetcher(client, loteria).fetch()


async def fetch_many(
    concursos: list[int], loteria: str = "mega", concurrency: int = 8
) -> tuple[list[dict], list[str]]:
    """Busca vários concursos em paralelo. Retorna (obtidos, erros)."""
    results: list[dict] = []
    errors: list[str] = []
    async with httpx.AsyncClient() as client:
        fetcher = Fetcher(client, loteria)
        sem = asyncio.Semaphore(concurrency)

        async def one(n: int) -> None:
            async with sem:
                try:
                    results.append(await fetcher.fetch(n))
                except FetchError as e:
                    errors.append(str(e))

        await asyncio.gather(*(one(n) for n in concursos))
    return results, errors
