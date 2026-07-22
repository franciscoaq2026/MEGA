from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .. import analysis, checker, db, generator, lotteries

router = APIRouter(tags=["jogos"])


def _lot(code: str | None) -> str:
    return lotteries.get_loteria(code)["code"]


def _somente_avancada(loteria: str) -> None:
    cfg = lotteries.get_loteria(loteria)
    if not cfg["avancada"]:
        raise HTTPException(
            409,
            f"recurso disponível apenas para loterias com análise avançada "
            f"(no momento, só a Mega-Sena); {cfg['nome']} não tem.",
        )


def _draws_or_409(loteria: str = "mega") -> list[dict]:
    draws = db.get_all_draws_asc(loteria)
    if not draws:
        raise HTTPException(409, "cache vazio: sincronize os sorteios primeiro")
    return draws


def _valida_dezenas(v: list[int], tamanho_min: int = 1) -> list[int]:
    if len(set(v)) != len(v) or not all(1 <= n <= 60 for n in v):
        raise ValueError("dezenas devem ser únicas e entre 1 e 60")
    return sorted(v)


class GenerateRequest(BaseModel):
    estrategia: Literal["aleatorio", "frequencia", "atrasados", "balanceado"]
    jogos: int = Field(1, ge=1, le=20)
    dezenas: int = Field(6, ge=1, le=50)
    anti_rateio: bool = False
    espelho: bool = False  # Lotomania: gera também o complemento (cobre os 100)


@router.get("/strategies")
def strategies():
    return {"estrategias": generator.ESTRATEGIAS}


def _com_espelho(jogos: list[dict], cfg: dict) -> list[dict]:
    """Para cada jogo, acrescenta o 'espelho' (as dezenas NÃO marcadas). Só faz
    sentido quando uma aposta cobre metade do volante (Lotomania: 50 de 100),
    de modo que jogo + espelho cobrem todas as dezenas.

    Fato matemático: jogo e espelho SEMPRE somam o total sorteado de acertos
    (ex.: 20). Isso amplia a chance de ganhar ALGUM prêmio (dois bilhetes que
    não se sobrepõem) e, se um fizer o acerto máximo, o outro faz 0 (e ambos
    pagam). NÃO aumenta a probabilidade do prêmio principal — essa é fixa."""
    pool = set(range(cfg["min_num"], cfg["max_num"] + 1))
    out: list[dict] = []
    for i, j in enumerate(jogos):
        base = dict(j, espelho=False, par=i)
        espelho_dz = sorted(pool - set(j["dezenas"]))
        espelho = {
            "dezenas": espelho_dz,
            "soma": sum(espelho_dz),
            "pares": sum(1 for n in espelho_dz if n % 2 == 0),
            "padroes_populares": [],
            "espelho": True,
            "par": i,
        }
        out.append(base)
        out.append(espelho)
    return out


@router.post("/generate")
def generate(req: GenerateRequest, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    cfg = lotteries.get_loteria(lot)
    dezenas = req.dezenas if cfg["escolher"] <= req.dezenas <= cfg["max_escolher"] else cfg["escolher"]
    draws = db.get_all_draws_asc(lot)
    if not draws and req.estrategia != "aleatorio":
        raise HTTPException(
            409,
            "cache vazio: sincronize os sorteios para usar estratégias baseadas no histórico "
            "(o aleatório puro funciona sem histórico)",
        )
    jogos = generator.gerar(draws, req.estrategia, req.jogos, dezenas, req.anti_rateio, loteria=lot)
    # Espelho: só quando uma aposta cobre metade do volante (2*escolher == total).
    espelho_ok = req.espelho and 2 * cfg["escolher"] == cfg["total"]
    if espelho_ok:
        jogos = _com_espelho(jogos, cfg)
    return {
        "estrategia": req.estrategia,
        "descricao": generator.ESTRATEGIAS[req.estrategia],
        "anti_rateio": req.anti_rateio,
        "espelho": espelho_ok,
        "jogos": jogos,
        "aviso": "Nenhuma estratégia altera a probabilidade real de acerto.",
    }


@router.get("/odds")
def odds(
    dezenas: int = Query(6, ge=6, le=20),
    preco_simples: float = Query(6.0, ge=0, le=1000),
    loteria: str | None = Query(default=None),
):
    _somente_avancada(_lot(loteria))
    return generator.odds(dezenas, preco_simples)


# ---- Fábrica de números: estatísticas avançadas, gerador, termômetro, fechamento ----


@router.get("/analysis/ranges")
def analysis_ranges(loteria: str | None = Query(default=None)):
    """Faixas típicas (p10–p90), média e desvio de cada indicador — base dos
    filtros inteligentes e do termômetro."""
    lot = _lot(loteria)
    _somente_avancada(lot)
    return analysis.historical_ranges(_draws_or_409(lot))


class Faixa(BaseModel):
    min: int | None = None
    max: int | None = None


class Filtros(BaseModel):
    soma: Faixa | None = None
    pares: Faixa | None = None
    primos: Faixa | None = None
    moldura: Faixa | None = None
    baixas: Faixa | None = None
    repetidas_anterior: Faixa | None = None
    consecutivos_max: int | None = Field(None, ge=1, le=6)

    def to_dict(self) -> dict:
        out: dict = {}
        for k in ("soma", "pares", "primos", "moldura", "baixas", "repetidas_anterior"):
            f = getattr(self, k)
            if f and (f.min is not None or f.max is not None):
                out[k] = [f.min, f.max]
        if self.consecutivos_max is not None:
            out["consecutivos_max"] = self.consecutivos_max
        return out


class GenerateAdvancedRequest(BaseModel):
    jogos: int = Field(3, ge=1, le=50)
    dezenas: int = Field(6, ge=6, le=20)
    filtros: Filtros = Filtros()
    incluir: list[int] = Field(default_factory=list)
    excluir: list[int] = Field(default_factory=list)
    anti_rateio: bool = False

    @field_validator("incluir", "excluir")
    @classmethod
    def _dz(cls, v):
        return _valida_dezenas(v)


@router.post("/generate-advanced")
def generate_advanced(req: GenerateAdvancedRequest, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    _somente_avancada(lot)
    draws = _draws_or_409(lot)
    try:
        resultado = generator.gerar_avancado(
            draws,
            jogos=req.jogos,
            dezenas=req.dezenas,
            filtros=req.filtros.to_dict(),
            incluir=req.incluir,
            excluir=req.excluir,
            anti_rateio=req.anti_rateio,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    resultado["aviso"] = "Filtros organizam padrões; não alteram a probabilidade de acerto."
    return resultado


class ScoreRequest(BaseModel):
    dezenas: list[int] = Field(min_length=6, max_length=20)

    @field_validator("dezenas")
    @classmethod
    def _dz(cls, v):
        return _valida_dezenas(v)


@router.post("/score")
def score(req: ScoreRequest, loteria: str | None = Query(default=None)):
    lot = _lot(loteria)
    _somente_avancada(lot)
    draws = _draws_or_409(lot)
    ranges = analysis.historical_ranges(draws)
    anterior = draws[-1]["dezenas"] if draws else None
    resultado = analysis.score(req.dezenas, ranges, anterior)
    resultado["aviso"] = (
        "O termômetro mede o quão típico é o jogo — não a chance de ganhar, "
        "que é idêntica para qualquer combinação."
    )
    return resultado


class WheelRequest(BaseModel):
    dezenas: list[int] = Field(min_length=7, max_length=20)
    tipo: Literal["completa", "reduzida"] = "reduzida"
    garantia: Literal[4, 5] = 4

    @field_validator("dezenas")
    @classmethod
    def _dz(cls, v):
        return _valida_dezenas(v)


@router.post("/wheel")
def wheel(req: WheelRequest, loteria: str | None = Query(default=None)):
    _somente_avancada(_lot(loteria))
    k = len(req.dezenas)
    if req.tipo == "completa":
        if k > 11:
            raise HTTPException(
                400,
                f"roda completa de {k} dezenas geraria {generator.comb(k, 6)} jogos; "
                "use até 11 dezenas na completa ou escolha o fechamento reduzido.",
            )
        return generator.roda_completa(req.dezenas)
    if k > 15:
        raise HTTPException(
            400, "fechamento reduzido aceita até 15 dezenas (acima disso fica lento)."
        )
    return generator.fechamento_reduzido(req.dezenas, req.garantia)


class Aposta(BaseModel):
    # Intervalo permissivo para cobrir todas as loterias (Mega 1–60, 6–20
    # dezenas; Lotomania 0–99, 50 dezenas). A conferência é só interseção.
    concurso: int = Field(ge=1)
    dezenas: list[int] = Field(min_length=6, max_length=50)

    @field_validator("dezenas")
    @classmethod
    def dezenas_validas(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v) or not all(0 <= n <= 99 for n in v):
            raise ValueError("dezenas devem ser únicas e estar entre 0 e 99")
        return sorted(v)


class CheckRequest(BaseModel):
    apostas: list[Aposta] = Field(max_length=500)


@router.post("/check")
def check(req: CheckRequest, loteria: str | None = Query(default=None)):
    """Confere apostas (guardadas no navegador) contra o cache de resultados."""
    lot = _lot(loteria)
    return {"resultados": checker.conferir_apostas([a.model_dump() for a in req.apostas], lot)}


@router.post("/backtest")
def backtest(
    ultimos: int = Query(100, ge=10, le=500),
    loteria: str | None = Query(default=None),
):
    """Teste honesto: joga cada estratégia nos últimos N concursos usando só
    o histórico anterior de cada um — mostra que nenhuma supera o acaso."""
    lot = _lot(loteria)
    _somente_avancada(lot)
    draws = db.get_all_draws_asc(lot)
    try:
        return checker.backtest(draws, ultimos)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
