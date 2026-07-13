"""Camada de acesso ao banco (cache dos sorteios + meta).

Dois backends, mesma interface:

- **SQLite local** (desenvolvimento e testes): arquivo em backend/data/.
- **Turso / libSQL** (produção serverless): banco remoto persistente, usado
  quando a variável de ambiente TURSO_DATABASE_URL está definida. Necessário
  no Vercel, onde o disco das funções é efêmero.

As consultas usam só o subconjunto comum da DB-API (placeholders "?",
cursor.description, execute/commit) para funcionar igual nos dois backends —
sem row_factory, executescript ou parâmetros nomeados.
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_CSV = DATA_DIR / "seed_megasena.csv"

TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
USE_TURSO = bool(TURSO_URL)

DB_PATH = os.environ.get("MEGASENA_DB_PATH") or str(DATA_DIR / "megasena.db")

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS draws (
        concurso INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        d1 INTEGER NOT NULL,
        d2 INTEGER NOT NULL,
        d3 INTEGER NOT NULL,
        d4 INTEGER NOT NULL,
        d5 INTEGER NOT NULL,
        d6 INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
)


def backend_name() -> str:
    return "turso" if USE_TURSO else "sqlite"


def get_conn():
    """Abre uma conexão nova. Para Turso, cada chamada abre um cliente HTTP
    curto (adequado ao modelo serverless)."""
    if USE_TURSO:
        import libsql  # importado só em produção (dependência opcional)

        return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    import sqlite3

    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _dicts(cursor) -> list[dict]:
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _query(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        return _dicts(cur)
    finally:
        conn.close()


def _write(statements: list[tuple[str, tuple]]) -> None:
    conn = get_conn()
    try:
        for sql, params in statements:
            conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    _write([(stmt, ()) for stmt in SCHEMA])
    if count_draws() == 0 and SEED_CSV.exists():
        from .csv_utils import parse_draws_csv

        rows, _errors = parse_draws_csv(SEED_CSV.read_text(encoding="utf-8"))
        if rows:
            upsert_draws(rows)


def row_to_draw(row: dict) -> dict:
    return {
        "concurso": row["concurso"],
        "data": row["data"],
        "dezenas": [row[f"d{i}"] for i in range(1, 7)],
    }


def upsert_draws(rows: list[dict]) -> int:
    sql = (
        "INSERT OR REPLACE INTO draws (concurso, data, d1, d2, d3, d4, d5, d6) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    statements = []
    for r in rows:
        dz = sorted(r["dezenas"])
        statements.append((sql, (r["concurso"], r["data"], *dz)))
    _write(statements)
    return len(rows)


def count_draws() -> int:
    return _query("SELECT COUNT(*) AS n FROM draws")[0]["n"]


def all_concursos() -> set[int]:
    return {r["concurso"] for r in _query("SELECT concurso FROM draws")}


def latest_local() -> dict | None:
    rows = _query("SELECT * FROM draws ORDER BY concurso DESC LIMIT 1")
    return row_to_draw(rows[0]) if rows else None


def get_draw(concurso: int) -> dict | None:
    rows = _query("SELECT * FROM draws WHERE concurso = ?", (concurso,))
    return row_to_draw(rows[0]) if rows else None


def list_draws(limit: int, offset: int) -> list[dict]:
    rows = _query(
        "SELECT * FROM draws ORDER BY concurso DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return [row_to_draw(r) for r in rows]


def get_all_draws_asc() -> list[dict]:
    rows = _query("SELECT * FROM draws ORDER BY concurso ASC")
    return [row_to_draw(r) for r in rows]


def set_meta(key: str, value) -> None:
    _write(
        [
            (
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
        ]
    )


def get_meta(key: str):
    rows = _query("SELECT value FROM meta WHERE key = ?", (key,))
    return json.loads(rows[0]["value"]) if rows else None
