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
# Histórico embutido no repositório (dezenas de todos os concursos + datas
# onde disponíveis). Serve de fonte para o /sync quando as APIs da Caixa/guidi
# estão inacessíveis — o caso do Vercel, cujo IP de datacenter é bloqueado.
SEED_JSON = DATA_DIR / "seed_megasena.json"

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
    # Login sem senha (magic link). Cada token é de uso único e expira.
    """
    CREATE TABLE IF NOT EXISTS login_tokens (
        token TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0
    )
    """,
    # Sessões ativas. account_id agrupa vários e-mails na mesma conta.
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        account_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
    # Apostas do usuário, sincronizadas entre aparelhos (por conta).
    """
    CREATE TABLE IF NOT EXISTS bets (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        concurso INTEGER NOT NULL,
        origem TEXT NOT NULL,
        estrategia TEXT,
        dezenas TEXT NOT NULL,
        criado_em TEXT NOT NULL
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


def load_bundled_seed() -> list[dict]:
    """Lê o histórico embutido (backend/data/seed_megasena.json)."""
    if not SEED_JSON.exists():
        return []
    data = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    return [
        {
            "concurso": int(r["concurso"]),
            "data": r.get("data") or "",
            "dezenas": sorted(int(d) for d in r["dezenas"]),
        }
        for r in data
    ]


def init_db() -> None:
    _write([(stmt, ()) for stmt in SCHEMA])
    # Auto-carrega o seed apenas no SQLite local (desenvolvimento). No Turso o
    # carregamento é feito em lotes pelo endpoint /sync, para não estourar o
    # tempo limite da função no primeiro cold start. Desligável nos testes.
    autoseed = os.environ.get("MEGASENA_AUTOSEED", "1") == "1"
    if autoseed and not USE_TURSO and count_draws() == 0:
        seed = load_bundled_seed()
        if seed:
            upsert_draws(seed)


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


def concursos_com_data() -> set[int]:
    """Concursos já salvos E com data preenchida. O sync usa isto para também
    completar a data de sorteios que entraram antes sem data."""
    return {
        r["concurso"]
        for r in _query("SELECT concurso FROM draws WHERE data != '' AND data IS NOT NULL")
    }


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


# ---- Autenticação sem senha (magic link) ----


def create_login_token(token: str, email: str, expires_at: str) -> None:
    _write(
        [
            (
                "INSERT INTO login_tokens (token, email, expires_at, used) VALUES (?, ?, ?, 0)",
                (token, email, expires_at),
            )
        ]
    )


def get_login_token(token: str) -> dict | None:
    rows = _query("SELECT * FROM login_tokens WHERE token = ?", (token,))
    return rows[0] if rows else None


def consume_login_token(token: str) -> None:
    _write([("UPDATE login_tokens SET used = 1 WHERE token = ?", (token,))])


def create_session(session_id: str, email: str, account_id: str, created_at: str, expires_at: str) -> None:
    _write(
        [
            (
                "INSERT INTO sessions (id, email, account_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, email, account_id, created_at, expires_at),
            )
        ]
    )


def get_session(session_id: str) -> dict | None:
    rows = _query("SELECT * FROM sessions WHERE id = ?", (session_id,))
    return rows[0] if rows else None


def delete_session(session_id: str) -> None:
    _write([("DELETE FROM sessions WHERE id = ?", (session_id,))])


# ---- Apostas sincronizadas (por conta) ----


def list_bets(account_id: str) -> list[dict]:
    rows = _query(
        "SELECT * FROM bets WHERE account_id = ? ORDER BY concurso DESC, criado_em DESC",
        (account_id,),
    )
    for r in rows:
        r["dezenas"] = json.loads(r["dezenas"])
    return rows


def upsert_bet(account_id: str, bet: dict) -> None:
    _write(
        [
            (
                "INSERT OR REPLACE INTO bets "
                "(id, account_id, concurso, origem, estrategia, dezenas, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    bet["id"],
                    account_id,
                    int(bet["concurso"]),
                    bet["origem"],
                    bet.get("estrategia"),
                    json.dumps(sorted(int(d) for d in bet["dezenas"])),
                    bet.get("criado_em") or "",
                ),
            )
        ]
    )


def upsert_bets(account_id: str, bets: list[dict]) -> int:
    statements = []
    for bet in bets:
        statements.append(
            (
                "INSERT OR REPLACE INTO bets "
                "(id, account_id, concurso, origem, estrategia, dezenas, criado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    bet["id"],
                    account_id,
                    int(bet["concurso"]),
                    bet["origem"],
                    bet.get("estrategia"),
                    json.dumps(sorted(int(d) for d in bet["dezenas"])),
                    bet.get("criado_em") or "",
                ),
            )
        )
    if statements:
        _write(statements)
    return len(statements)


def delete_bet(account_id: str, bet_id: str) -> None:
    _write([("DELETE FROM bets WHERE account_id = ? AND id = ?", (account_id, bet_id))])
