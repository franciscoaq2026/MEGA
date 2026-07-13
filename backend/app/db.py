"""Camada de acesso ao SQLite.

O banco é um cache local dos sorteios (dado público, re-obtível da API).
Em plataformas serverless (Vercel) o disco é efêmero: usamos /tmp e o banco
é repovoado a partir do seed embutido no repositório a cada cold start.
"""

import json
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_CSV = DATA_DIR / "seed_megasena.csv"


def _default_db_path() -> str:
    if os.environ.get("VERCEL"):
        return "/tmp/megasena.db"
    return str(DATA_DIR / "megasena.db")


DB_PATH = os.environ.get("MEGASENA_DB_PATH") or _default_db_path()

SCHEMA = """
CREATE TABLE IF NOT EXISTS draws (
    concurso INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    d1 INTEGER NOT NULL,
    d2 INTEGER NOT NULL,
    d3 INTEGER NOT NULL,
    d4 INTEGER NOT NULL,
    d5 INTEGER NOT NULL,
    d6 INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    if count_draws() == 0 and SEED_CSV.exists():
        from .csv_utils import parse_draws_csv

        rows, _errors = parse_draws_csv(SEED_CSV.read_text(encoding="utf-8"))
        if rows:
            upsert_draws(rows)


def row_to_draw(row: sqlite3.Row) -> dict:
    return {
        "concurso": row["concurso"],
        "data": row["data"],
        "dezenas": [row[f"d{i}"] for i in range(1, 7)],
    }


def upsert_draws(rows: list[dict]) -> int:
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO draws (concurso, data, d1, d2, d3, d4, d5, d6)
            VALUES (:concurso, :data, :d1, :d2, :d3, :d4, :d5, :d6)
            """,
            [
                {
                    "concurso": r["concurso"],
                    "data": r["data"],
                    **{f"d{i}": d for i, d in enumerate(sorted(r["dezenas"]), start=1)},
                }
                for r in rows
            ],
        )
    return len(rows)


def count_draws() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]


def all_concursos() -> set[int]:
    with get_conn() as conn:
        return {r[0] for r in conn.execute("SELECT concurso FROM draws")}


def latest_local() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM draws ORDER BY concurso DESC LIMIT 1"
        ).fetchone()
    return row_to_draw(row) if row else None


def get_draw(concurso: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM draws WHERE concurso = ?", (concurso,)
        ).fetchone()
    return row_to_draw(row) if row else None


def list_draws(limit: int, offset: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM draws ORDER BY concurso DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [row_to_draw(r) for r in rows]


def get_all_draws_asc() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM draws ORDER BY concurso ASC").fetchall()
    return [row_to_draw(r) for r in rows]


def set_meta(key: str, value) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )


def get_meta(key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None
