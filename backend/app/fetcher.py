"""Busca de resultados nas APIs públicas.

Fonte principal: API da Caixa (a mesma usada pelo site oficial de loterias).
Fallback: api.guidi.dev.br, que espelha o mesmo formato de payload.
"""

import asyncio
from datetime import datetime

import httpx

CAIXA_BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena"
GUIDI_BASE = "https://api.guidi.dev.br/loteria/megasena"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (megasena-stats; uso pessoal)",
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


def parse_payload(data: dict) -> dict:
    """Normaliza o payload da Caixa/guidi para o formato interno."""
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
    if len(set(dezenas)) != 6 or not all(1 <= d <= 60 for d in dezenas):
        raise FetchError(f"dezenas inválidas no payload: {dezenas_raw}")
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

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.caixa_ok = True

    def _urls(self, concurso: int | None) -> list[str]:
        caixa = f"{CAIXA_BASE}/{concurso}" if concurso else CAIXA_BASE
        guidi = f"{GUIDI_BASE}/{concurso}" if concurso else f"{GUIDI_BASE}/ultimo"
        return [caixa, guidi] if self.caixa_ok else [guidi, caixa]

    async def fetch(self, concurso: int | None = None) -> dict:
        last_error: Exception | None = None
        for url in self._urls(concurso):
            try:
                resp = await self.client.get(url, headers=HEADERS, timeout=TIMEOUT)
                resp.raise_for_status()
                return parse_payload(resp.json())
            except Exception as e:  # noqa: BLE001 - qualquer falha aciona o fallback
                if url.startswith(CAIXA_BASE):
                    self.caixa_ok = False
                last_error = e
        raise FetchError(
            f"concurso {concurso or 'último'}: nenhuma API respondeu ({last_error})"
        )


async def fetch_latest() -> dict:
    async with httpx.AsyncClient() as client:
        return await Fetcher(client).fetch()


async def fetch_many(concursos: list[int], concurrency: int = 8) -> tuple[list[dict], list[str]]:
    """Busca vários concursos em paralelo. Retorna (obtidos, erros)."""
    results: list[dict] = []
    errors: list[str] = []
    async with httpx.AsyncClient() as client:
        fetcher = Fetcher(client)
        sem = asyncio.Semaphore(concurrency)

        async def one(n: int) -> None:
            async with sem:
                try:
                    results.append(await fetcher.fetch(n))
                except FetchError as e:
                    errors.append(str(e))

        await asyncio.gather(*(one(n) for n in concursos))
    return results, errors
