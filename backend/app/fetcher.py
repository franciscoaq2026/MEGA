"""Busca de resultados.

Duas famílias de fonte:

- **API da Caixa** (fallback: api.guidi.dev.br, mesmo formato de payload):
  resultado oficial minutos após o sorteio, com data e prêmio do próximo
  concurso. Só responde a quem tem IP residencial no Brasil — a Caixa recusa
  o Vercel, e a guidi passou a aceitar apenas IPs brasileiros em 12/07/2026.
  Quem a usa é o navegador do usuário (Sorteios → /import-payloads) e o
  seed_turso.py rodado de casa (classe Fetcher abaixo).
- **Espelhos no GitHub** (ESPELHOS): o histórico completo em JSON, atualizado
  todo dia por GitHub Actions a partir da própria API da Caixa. O
  raw.githubusercontent.com responde de qualquer lugar, então é a fonte do
  servidor (/sync e o cron diário).
"""

import asyncio
import time
from datetime import datetime

import httpx

from . import lotteries

CAIXA_API = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
GUIDI_API = "https://api.guidi.dev.br/loteria"

# Espelhos por slug da loteria. O primeiro é o principal; os demais completam
# o que ele ainda não tiver. Conferidos em 23/10/2026: idênticos ao histórico
# embutido em todos os concursos em comum (2.994 da Mega, 3.657 da Lotofácil),
# sem buracos na numeração. O maickon/free-apiloterias, usado antes, parou em
# 09/04/2026.
ESPELHOS: dict[str, list[str]] = {
    "megasena": [
        "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/mega-sena.json",
    ],
    "lotofacil": [
        "https://raw.githubusercontent.com/eitchtee/loterias.json/main/data/lotofacil.json",
        "https://raw.githubusercontent.com/rjaugusto/lotofacil-dados/main/historico.json",
    ],
}
ESPELHO_TIMEOUT = httpx.Timeout(30.0)
# O /sync roda em lotes (o frontend repete a chamada até remaining == 0) e,
# sem cache, cada lote baixaria de novo 0,5 a 2 MB. O próprio raw do GitHub
# já guarda o arquivo por 5 minutos, então 2 minutos aqui não atrasam nada.
ESPELHO_CACHE_SEGUNDOS = 120
_cache_espelhos: dict[str, tuple[float, list[dict], list[str]]] = {}

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
        or data.get("resultado")  # espelho eitchtee
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
    """Cliente da Caixa com fallback na guidi: se a Caixa falhar, passa a usar
    a guidi nas próximas chamadas da mesma sessão. Só funciona de IP
    residencial brasileiro — por isso só o seed_turso.py o usa."""

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
        return [caixa, guidi] if self.caixa_ok else [guidi, caixa]

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


def ler_espelho(dados, loteria: str = "mega") -> tuple[list[dict], int]:
    """Converte o JSON de um espelho em sorteios no formato interno.

    Aceita os dois formatos em uso: lista de {concurso, data, resultado}
    (eitchtee) e {historico: [{numero, dataApuracao, dezenas}]} (rjaugusto).
    Cada registro passa pelo mesmo parse_payload das fontes oficiais.
    Devolve (sorteios, quantos registros inválidos foram ignorados)."""
    registros = dados.get("historico") if isinstance(dados, dict) else dados
    if not isinstance(registros, list):
        raise FetchError("espelho em formato desconhecido")
    sorteios: list[dict] = []
    invalidos = 0
    for r in registros:
        try:
            s = parse_payload(r, loteria)
        except Exception:  # noqa: BLE001 - um registro estragado não derruba o espelho
            invalidos += 1
            continue
        sorteios.append({"concurso": s["concurso"], "data": s["data"], "dezenas": s["dezenas"]})
    return sorteios, invalidos


async def fetch_espelhos(loteria: str = "mega") -> tuple[list[dict], list[str]]:
    """Baixa os espelhos da loteria e junta tudo num histórico só.

    Devolve (sorteios em ordem de concurso, avisos). Um concurso que dois
    espelhos trazem com dezenas ou data diferentes fica de fora: melhor faltar
    do que gravar o errado — ele entra pela Caixa, no navegador."""
    cfg = lotteries.get_loteria(loteria)
    agora = time.monotonic()
    em_cache = _cache_espelhos.get(cfg["code"])
    if em_cache and agora - em_cache[0] < ESPELHO_CACHE_SEGUNDOS:
        return em_cache[1], em_cache[2]

    urls = ESPELHOS.get(cfg["fonte"], [])

    async def baixar(client: httpx.AsyncClient, url: str):
        resp = await client.get(url, headers=HEADERS, timeout=ESPELHO_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    async with httpx.AsyncClient() as client:
        respostas = await asyncio.gather(*(baixar(client, u) for u in urls), return_exceptions=True)

    avisos: list[str] = []
    juntos: dict[int, dict] = {}
    divergentes: set[int] = set()
    for url, resp in zip(urls, respostas):
        dono = url.split("/")[3]  # raw.githubusercontent.com/<dono>/<repo>/...
        try:
            if isinstance(resp, Exception):
                raise resp
            sorteios, invalidos = ler_espelho(resp, cfg["code"])
        except Exception as e:  # noqa: BLE001 - um espelho fora do ar não derruba os outros
            avisos.append(f"espelho {dono}: {e}")
            continue
        if invalidos:
            avisos.append(f"espelho {dono}: {invalidos} registro(s) inválido(s) ignorado(s)")
        for s in sorteios:
            atual = juntos.setdefault(s["concurso"], s)
            if atual["dezenas"] != s["dezenas"] or atual["data"] != s["data"]:
                divergentes.add(s["concurso"])
    for n in divergentes:
        del juntos[n]
    if divergentes:
        avisos.append(
            f"espelhos divergem em {len(divergentes)} concurso(s), ignorados: {sorted(divergentes)[:5]}"
        )
    sorteios = sorted(juntos.values(), key=lambda s: s["concurso"])
    if sorteios:  # só guarda sucesso: uma falha de rede não fica presa por 2 minutos
        _cache_espelhos[cfg["code"]] = (agora, sorteios, avisos)
    return sorteios, avisos
