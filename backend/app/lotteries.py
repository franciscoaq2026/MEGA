"""Registro central das loterias suportadas (arquitetura de hub).

Tudo o que é específico de cada jogo fica descrito aqui, de forma que o
restante do backend (geração, conferência, estatística, busca) seja
parametrizado por loteria em vez de assumir "6 de 60".

- mega  → Mega-Sena: escolhe 6 de 60 (1–60), sorteia 6.
- loto  → Lotomania: escolhe 50 de 100 (00–99), sorteia 20; premia
          20/19/18/17/16/15 e também 0 acertos.
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
        "cols": 10,            # colunas do volante (grade 6x10)
        "avancada": True,      # tem "Fábrica"/termômetro calibrados
    },
    "loto": {
        "code": "loto",
        "nome": "Lotomania",
        "min_num": 0,
        "max_num": 99,
        "total": 100,
        "escolher": 50,
        "max_escolher": 50,   # a Lotomania é sempre 50 dezenas fixas
        "sorteadas": 20,
        # 0 acertos também premia (mesma dificuldade que 20)
        "faixas": {20: "20 acertos", 19: "19 acertos", 18: "18 acertos",
                   17: "17 acertos", 16: "16 acertos", 15: "15 acertos",
                   0: "0 acertos"},
        "fonte": "lotomania",
        "cols": 10,            # grade 10x10 (00–99)
        "avancada": False,     # análise avançada específica virá depois
    },
}

DEFAULT = "mega"


def get_loteria(code: str | None) -> dict:
    """Retorna a config da loteria; cai na Mega se o código for vazio/inválido."""
    return LOTERIAS.get((code or DEFAULT).lower(), LOTERIAS[DEFAULT])


def is_valid(code: str | None) -> bool:
    return (code or "").lower() in LOTERIAS
