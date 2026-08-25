"""Leitura de CSV de sorteios (importação manual e seed embutido).

Formato esperado: colunas concurso, data, dezena1..dezenaN — onde N é o número
de dezenas que a loteria sorteia (6 na Mega, 15 na Lotofácil). Com ou sem
cabeçalho; separador ; ou ,. Datas em dd/mm/aaaa ou aaaa-mm-dd.
Colunas extras depois das dezenas são ignoradas.

O parser é parametrizado pela loteria de destino de propósito: antes ele lia
sempre 6 colunas e aceitava 1–60, então um CSV da Lotofácil entrava TRUNCADO
(as 6 primeiras dezenas de 15) e sem erro nenhum — corrompendo silenciosamente
a base sobre a qual todo o resto do app calcula.
"""

import csv
import io
import re
from datetime import datetime

from . import lotteries

DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y")

# Nomes que um cabeçalho usa para as colunas de dezenas — inclui "bola", que é
# como a própria Caixa nomeia na planilha oficial de resultados.
_COLUNA_DEZENA = re.compile(r"^\s*(dezena|bola|n[uú]mero|num|d|b|n)\s*[-_ ]?\d*\s*$", re.I)


def _parse_date(value: str) -> str:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {value!r}")


def _parse_row(cols: list[str], cfg: dict) -> dict:
    n = cfg["sorteadas"]
    lo, hi = cfg["min_num"], cfg["max_num"]
    if len(cols) < 2 + n:
        raise ValueError(
            f"linha com menos de {2 + n} colunas (concurso, data, {n} dezenas)"
        )
    concurso = int(cols[0].strip())
    if concurso <= 0:
        raise ValueError(f"concurso inválido: {cols[0]!r}")
    data = _parse_date(cols[1])
    dezenas = [int(c.strip()) for c in cols[2 : 2 + n]]
    if len(set(dezenas)) != n or not all(lo <= d <= hi for d in dezenas):
        raise ValueError(
            f"dezenas inválidas para {cfg['nome']} "
            f"(esperado {n} dezenas únicas entre {lo} e {hi}): {cols[2 : 2 + n]}"
        )
    return {"concurso": concurso, "data": data, "dezenas": sorted(dezenas)}


def _confere_cabecalho(cols: list[str], cfg: dict) -> None:
    """Recusa o arquivo quando o cabeçalho descreve OUTRA loteria.

    Colunas extras depois das dezenas são ignoradas de propósito (a planilha
    da Caixa traz ganhadores, rateio, cidade…), mas isso significa que um
    arquivo de 15 dezenas importado como Mega entraria truncado nas 6
    primeiras. Quando o arquivo se descreve, dá para impedir: se ele nomeia
    um número de colunas de dezenas diferente do que a loteria sorteia, é o
    arquivo errado.
    """
    n = sum(1 for c in cols if _COLUNA_DEZENA.match(c))
    if n and n != cfg["sorteadas"]:
        raise ValueError(
            f"o cabeçalho descreve {n} dezenas por sorteio, e a {cfg['nome']} "
            f"sorteia {cfg['sorteadas']} — este CSV parece ser de outra loteria"
        )


def parse_draws_csv(text: str, loteria: str = "mega") -> tuple[list[dict], list[str]]:
    """Retorna (linhas válidas, mensagens de erro) no formato da loteria dada.

    Cabeçalho é detectado automaticamente (primeira linha cujo 1º campo não é
    número é pulada) e, quando existe, serve para recusar o arquivo de outra
    loteria antes de importar qualquer linha."""
    cfg = lotteries.get_loteria(loteria)
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows: list[dict] = []
    errors: list[str] = []
    for i, cols in enumerate(reader, start=1):
        if not cols or not any(c.strip() for c in cols):
            continue
        if i == 1 and not cols[0].strip().isdigit():
            try:
                _confere_cabecalho(cols, cfg)
            except ValueError as e:
                return [], [f"linha 1: {e}"]
            continue  # cabeçalho
        try:
            rows.append(_parse_row(cols, cfg))
        except (ValueError, IndexError) as e:
            errors.append(f"linha {i}: {e}")
    return rows, errors
