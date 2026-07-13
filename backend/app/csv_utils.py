"""Leitura de CSV de sorteios (importação manual e seed embutido).

Formato esperado: colunas concurso, data, dezena1..dezena6 (com ou sem
cabeçalho; separador ; ou ,). Datas em dd/mm/aaaa ou aaaa-mm-dd.
Colunas extras após as 8 primeiras são ignoradas.
"""

import csv
import io
from datetime import datetime

DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y")


def _parse_date(value: str) -> str:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {value!r}")


def _parse_row(cols: list[str]) -> dict:
    if len(cols) < 8:
        raise ValueError("linha com menos de 8 colunas (concurso, data, 6 dezenas)")
    concurso = int(cols[0].strip())
    if concurso <= 0:
        raise ValueError(f"concurso inválido: {cols[0]!r}")
    data = _parse_date(cols[1])
    dezenas = [int(c.strip()) for c in cols[2:8]]
    if len(set(dezenas)) != 6 or not all(1 <= d <= 60 for d in dezenas):
        raise ValueError(f"dezenas inválidas: {cols[2:8]}")
    return {"concurso": concurso, "data": data, "dezenas": sorted(dezenas)}


def parse_draws_csv(text: str) -> tuple[list[dict], list[str]]:
    """Retorna (linhas válidas, mensagens de erro). Cabeçalho é detectado
    automaticamente (primeira linha cujo 1º campo não é número é pulada)."""
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows: list[dict] = []
    errors: list[str] = []
    for i, cols in enumerate(reader, start=1):
        if not cols or not any(c.strip() for c in cols):
            continue
        if i == 1 and not cols[0].strip().isdigit():
            continue  # cabeçalho
        try:
            rows.append(_parse_row(cols))
        except (ValueError, IndexError) as e:
            errors.append(f"linha {i}: {e}")
    return rows, errors
