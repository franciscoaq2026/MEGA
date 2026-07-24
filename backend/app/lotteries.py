"""Registro central das loterias suportadas (arquitetura de hub).

Tudo o que é específico de cada jogo fica descrito aqui, de forma que o
restante do backend (geração, conferência, estatística, busca, fechamento)
seja parametrizado por loteria em vez de assumir "6 de 60".

- mega  → Mega-Sena: escolhe 6 de 60 (1–60), sorteia 6.
- lofa  → Lotofácil: escolhe 15 de 25 (1–25), sorteia 15; premia 15/14/13/12/11.

Chaves de configuração:

- ``cols``            colunas do volante; ``linhas`` sai de ``total // cols``.
                      Define moldura/miolo em analysis.py.
- ``preco``           preço da aposta simples (usado no custo do fechamento).
- ``avancada``        habilita Fábrica (filtros, termômetro, fechamento).
- ``max_roda_completa``/``max_reduzida``  limites de dezenas no fechamento,
                      calibrados para o número de combinações não explodir.
"""

LOTERIAS: dict[str, dict] = {
    "mega": {
        "code": "mega",
        "nome": "Mega-Sena",
        "min_num": 1,
        "max_num": 60,
        "total": 60,
        "escolher": 6,   # dezenas numa aposta simples
        "max_escolher": 20,  # limite de dezenas por aposta (fechamento)
        "sorteadas": 6,  # dezenas sorteadas
        # faixas de premiação: nº de acertos -> rótulo
        "faixas": {6: "sena", 5: "quina", 4: "quadra"},
        "fonte": "megasena",   # slug nas APIs da Caixa/guidi
        "cols": 10,            # grade 6x10
        "preco": 6.00,
        "avancada": True,      # tem "Fábrica"/termômetro calibrados
        "max_roda_completa": 11,   # C(11,6) = 462 jogos
        "max_reduzida": 15,        # C(15,6) = 5.005 combinações a cobrir
        # A partir de quantos consecutivos o jogo vira "desenho no volante"
        # (padrão popular → risco de rateio). Marcar 6 de 60 raramente encosta
        # em 4 seguidos, então 4 já é suspeito.
        "consecutivos_populares": 4,
    },
    "lofa": {
        "code": "lofa",
        "nome": "Lotofácil",
        "min_num": 1,
        "max_num": 25,
        "total": 25,
        "escolher": 15,
        "max_escolher": 20,   # a Caixa aceita de 15 a 20 dezenas
        "sorteadas": 15,
        "faixas": {15: "15 acertos", 14: "14 acertos", 13: "13 acertos",
                   12: "12 acertos", 11: "11 acertos"},
        "fonte": "lotofacil",
        "cols": 5,             # grade 5x5
        "preco": 3.50,
        "avancada": True,
        "max_roda_completa": 17,   # C(17,15) = 136 jogos
        "max_reduzida": 18,        # C(18,15) = 816 combinações a cobrir
        # Marcar 15 de 25 SEMPRE gera sequências — não cabem 15 dezenas em 25
        # sem encostar. Medido nos 3.657 concursos do seed: 4+ seguidos saem em
        # 87% dos sorteios (usar o 4 da Mega marcaria quase todo jogo), 9+ em
        # 2,2% — a mesma ordem de raridade que o 4 representa na Mega (0,2%).
        "consecutivos_populares": 9,
    },
}

DEFAULT = "mega"


def get_loteria(code: str | None) -> dict:
    """Retorna a config da loteria; cai na Mega se o código for vazio/inválido."""
    return LOTERIAS.get((code or DEFAULT).lower(), LOTERIAS[DEFAULT])


def is_valid(code: str | None) -> bool:
    return (code or "").lower() in LOTERIAS


def numbers(cfg: dict) -> list[int]:
    """Pool completo de dezenas da loteria, em ordem."""
    return list(range(cfg["min_num"], cfg["max_num"] + 1))


def linhas(cfg: dict) -> int:
    """Linhas do volante (para moldura/miolo)."""
    return -(-cfg["total"] // cfg["cols"])  # divisão para cima


def faixa_maxima(cfg: dict) -> int:
    """Nº de acertos da faixa principal (sena, 15 acertos, ...)."""
    return max(cfg["faixas"])
