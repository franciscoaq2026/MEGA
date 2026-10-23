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
# Histórico embutido no repositório por loteria (dezenas de todos os concursos
# + datas onde disponíveis). Serve de fonte para o /sync quando as APIs da
# Caixa/guidi estão inacessíveis — o caso do Vercel, cujo IP de datacenter é
# bloqueado. Ambas trazem o histórico completo até a data do último build; o
# que vier depois entra pelo /sync.
SEED_FILES = {
    "mega": DATA_DIR / "seed_megasena.json",
    "lofa": DATA_DIR / "seed_lotofacil.json",
}

TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
USE_TURSO = bool(TURSO_URL)

DB_PATH = os.environ.get("MEGASENA_DB_PATH") or str(DATA_DIR / "megasena.db")

SCHEMA = (
    # Tabela legada da Mega (6 colunas). Mantida só como fonte de migração
    # para a tabela genérica lottery_draws; novas escritas vão para a genérica.
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
    # Sorteios de qualquer loteria: dezenas guardadas como JSON (a Lotofácil
    # tem 15 números; a Mega, 6). Chave composta (loteria, concurso).
    """
    CREATE TABLE IF NOT EXISTS lottery_draws (
        loteria TEXT NOT NULL,
        concurso INTEGER NOT NULL,
        data TEXT NOT NULL,
        dezenas TEXT NOT NULL,
        PRIMARY KEY (loteria, concurso)
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
    # Apostas do usuário, sincronizadas entre aparelhos (por conta e loteria).
    """
    CREATE TABLE IF NOT EXISTS bets (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        loteria TEXT NOT NULL DEFAULT 'mega',
        concurso INTEGER NOT NULL,
        origem TEXT NOT NULL,
        estrategia TEXT,
        dezenas TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        espalhar INTEGER,
        espalhar_deduzido INTEGER
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


def load_bundled_seed(loteria: str = "mega") -> list[dict]:
    """Lê o histórico embutido da loteria (backend/data/seed_<loteria>.json)."""
    path = SEED_FILES.get(loteria)
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {
            "concurso": int(r["concurso"]),
            "data": r.get("data") or "",
            "dezenas": sorted(int(d) for d in r["dezenas"]),
        }
        for r in data
    ]


def _migrate_legacy_draws() -> None:
    """Copia a tabela antiga `draws` (Mega, 6 colunas) para a genérica
    lottery_draws sob a loteria 'mega', uma única vez. Idempotente: só roda
    se a genérica ainda não tiver dados de Mega e a antiga tiver linhas."""
    ja_tem = _query("SELECT COUNT(*) AS n FROM lottery_draws WHERE loteria = 'mega'")[0]["n"]
    if ja_tem:
        return
    try:
        antigos = _query("SELECT * FROM draws")
    except Exception:  # noqa: BLE001 - tabela antiga pode não existir
        return
    if not antigos:
        return
    rows = [
        {
            "concurso": r["concurso"],
            "data": r["data"],
            "dezenas": [r[f"d{i}"] for i in range(1, 7)],
        }
        for r in antigos
    ]
    upsert_draws(rows, "mega")


# Loterias que já existiram no app e foram removidas. Os dados delas — cache
# de sorteios, meta e APOSTAS DO USUÁRIO — são apagados uma única vez, com
# marcador em `meta` para não repetir a cada inicialização.
#
# A lista é explícita de propósito: purgar "toda loteria não registrada" faria
# um erro de digitação em lotteries.py destruir dados de verdade.
LOTERIAS_REMOVIDAS = ("loto",)  # Lotomania — substituída pela Lotofácil


def _purge_loterias_removidas() -> None:
    feito = get_meta("purge_loterias") or []
    pendentes = [c for c in LOTERIAS_REMOVIDAS if c not in feito]
    if not pendentes:
        return
    for code in pendentes:
        try:
            sorteios = _query(
                "SELECT COUNT(*) AS n FROM lottery_draws WHERE loteria = ?", (code,)
            )[0]["n"]
            apostas = _query("SELECT COUNT(*) AS n FROM bets WHERE loteria = ?", (code,))[0]["n"]
            _write(
                [
                    ("DELETE FROM lottery_draws WHERE loteria = ?", (code,)),
                    ("DELETE FROM bets WHERE loteria = ?", (code,)),
                    ("DELETE FROM meta WHERE key = ?", (f"proximo:{code}",)),
                ]
            )
            print(f"[init_db] loteria removida '{code}': apagados {sorteios} sorteios e {apostas} aposta(s)")
        except Exception as exc:  # noqa: BLE001 - não derruba o init
            print(f"[init_db] aviso ao limpar '{code}': {exc}")
            return
    set_meta("purge_loterias", sorted(set(feito) | set(pendentes)))


# Colunas que entraram na tabela bets depois de ela já existir em produção.
# CREATE TABLE IF NOT EXISTS não altera uma tabela antiga, então cada uma é
# acrescentada aqui se faltar.
_BETS_COLUNAS_NOVAS = (
    ("loteria", "TEXT NOT NULL DEFAULT 'mega'"),  # suporte multi-loteria
    ("espalhar", "INTEGER"),  # 1/0 = ligado/desligado; NULL = não se aplica ou não registrado
    ("espalhar_deduzido", "INTEGER"),  # 1 = valor veio do estudo, não da hora em que foi salvo
)


def _ensure_bets_columns() -> None:
    """Adiciona às bets as colunas que bancos antigos não têm. Idempotente."""
    try:
        cols = {r["name"] for r in _query("PRAGMA table_info(bets)")}
    except Exception:  # noqa: BLE001
        return
    if not cols:
        return
    for nome, tipo in _BETS_COLUNAS_NOVAS:
        if nome in cols:
            continue
        try:
            _write([(f"ALTER TABLE bets ADD COLUMN {nome} {tipo}", ())])
        except Exception as exc:  # noqa: BLE001 - não derruba o init
            print(f"[init_db] aviso ao migrar bets.{nome}: {exc}")


# Status do Espalhar dos jogos salvos antes de o campo existir, deduzido pela
# sobreposição das dezenas dentro de cada lote (estudo de 23/10/2026).
BACKFILL_ESPALHAR = DATA_DIR / "espalhar_deduzido.json"


def _backfill_espalhar() -> None:
    """Grava, uma única vez por versão do arquivo, o Espalhar deduzido dos
    jogos antigos. Só preenche jogos ainda sem o campo: o que foi gravado na
    hora nunca é sobrescrito."""
    if not BACKFILL_ESPALHAR.exists():
        return
    try:
        dados = json.loads(BACKFILL_ESPALHAR.read_text(encoding="utf-8"))
        chave = f"backfill_espalhar:{dados.get('versao', 1)}"
        if get_meta(chave):
            return
        jogos = dados["jogos"]
        _write(
            [
                (
                    "UPDATE bets SET espalhar = ?, espalhar_deduzido = ? "
                    "WHERE id = ? AND espalhar IS NULL",
                    (int(bool(j["espalhar"])), int(bool(j["deduzido"])), j["id"]),
                )
                for j in jogos
            ]
        )
        set_meta(chave, {"jogos": len(jogos)})
    except Exception as exc:  # noqa: BLE001 - não derruba o init
        print(f"[init_db] aviso no backfill do espalhar: {exc}")


def init_db() -> None:
    _write([(stmt, ()) for stmt in SCHEMA])
    _migrate_legacy_draws()
    _ensure_bets_columns()
    _backfill_espalhar()
    _purge_loterias_removidas()
    # Auto-carrega o seed apenas no SQLite local (desenvolvimento). No Turso o
    # carregamento é feito em lotes pelo endpoint /sync, para não estourar o
    # tempo limite da função no primeiro cold start. Desligável nos testes.
    autoseed = os.environ.get("MEGASENA_AUTOSEED", "1") == "1"
    if autoseed and not USE_TURSO:
        for loteria in SEED_FILES:
            if count_draws(loteria) == 0:
                seed = load_bundled_seed(loteria)
                if seed:
                    upsert_draws(seed, loteria)


def upsert_draws(rows: list[dict], loteria: str = "mega") -> int:
    sql = (
        "INSERT OR REPLACE INTO lottery_draws (loteria, concurso, data, dezenas) "
        "VALUES (?, ?, ?, ?)"
    )
    statements = []
    for r in rows:
        dz = sorted(int(d) for d in r["dezenas"])
        statements.append((sql, (loteria, r["concurso"], r["data"], json.dumps(dz))))
    if statements:
        _write(statements)
    return len(rows)


def _row_to_draw(row: dict) -> dict:
    return {
        "concurso": row["concurso"],
        "data": row["data"],
        "dezenas": json.loads(row["dezenas"]),
    }


def count_draws(loteria: str = "mega") -> int:
    return _query(
        "SELECT COUNT(*) AS n FROM lottery_draws WHERE loteria = ?", (loteria,)
    )[0]["n"]


def all_concursos(loteria: str = "mega") -> set[int]:
    return {
        r["concurso"]
        for r in _query("SELECT concurso FROM lottery_draws WHERE loteria = ?", (loteria,))
    }


def concursos_com_data(loteria: str = "mega") -> set[int]:
    """Concursos já salvos E com data preenchida. O sync usa isto para também
    completar a data de sorteios que entraram antes sem data."""
    return {
        r["concurso"]
        for r in _query(
            "SELECT concurso FROM lottery_draws WHERE loteria = ? "
            "AND data != '' AND data IS NOT NULL",
            (loteria,),
        )
    }


def latest_local(loteria: str = "mega") -> dict | None:
    rows = _query(
        "SELECT * FROM lottery_draws WHERE loteria = ? ORDER BY concurso DESC LIMIT 1",
        (loteria,),
    )
    return _row_to_draw(rows[0]) if rows else None


def get_draw(concurso: int, loteria: str = "mega") -> dict | None:
    rows = _query(
        "SELECT * FROM lottery_draws WHERE loteria = ? AND concurso = ?",
        (loteria, concurso),
    )
    return _row_to_draw(rows[0]) if rows else None


def list_draws(limit: int, offset: int, loteria: str = "mega") -> list[dict]:
    rows = _query(
        "SELECT * FROM lottery_draws WHERE loteria = ? ORDER BY concurso DESC LIMIT ? OFFSET ?",
        (loteria, limit, offset),
    )
    return [_row_to_draw(r) for r in rows]


def get_all_draws_asc(loteria: str = "mega") -> list[dict]:
    rows = _query(
        "SELECT * FROM lottery_draws WHERE loteria = ? ORDER BY concurso ASC",
        (loteria,),
    )
    return [_row_to_draw(r) for r in rows]


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


# ---- Apostas sincronizadas (por conta e loteria) ----

# Upsert por id. O Espalhar usa COALESCE: um aparelho com a cópia antiga do
# jogo (sem o campo) reenvia null a cada sync, e isso não pode apagar o valor
# que o servidor já tem — gravado na hora ou preenchido pelo estudo. O WHERE
# impede que um id de outra conta sobrescreva o jogo.
_BET_INSERT = (
    "INSERT INTO bets "
    "(id, account_id, loteria, concurso, origem, estrategia, dezenas, criado_em, "
    "espalhar, espalhar_deduzido) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(id) DO UPDATE SET "
    "loteria = excluded.loteria, concurso = excluded.concurso, origem = excluded.origem, "
    "estrategia = excluded.estrategia, dezenas = excluded.dezenas, "
    "criado_em = excluded.criado_em, "
    "espalhar = COALESCE(excluded.espalhar, bets.espalhar), "
    "espalhar_deduzido = CASE WHEN excluded.espalhar IS NULL "
    "THEN bets.espalhar_deduzido ELSE excluded.espalhar_deduzido END "
    "WHERE bets.account_id = excluded.account_id"
)


def _bet_params(account_id: str, bet: dict) -> tuple:
    return (
        bet["id"],
        account_id,
        (bet.get("loteria") or "mega"),
        int(bet["concurso"]),
        bet["origem"],
        bet.get("estrategia"),
        json.dumps(sorted(int(d) for d in bet["dezenas"])),
        bet.get("criado_em") or "",
        None if bet.get("espalhar") is None else int(bool(bet["espalhar"])),
        None if bet.get("espalhar") is None else int(bool(bet.get("espalhar_deduzido"))),
    )


def list_bets(account_id: str, loteria: str | None = None) -> list[dict]:
    """Lista apostas da conta. Se `loteria` for dado, filtra por ela;
    caso contrário retorna todas (de todas as loterias)."""
    if loteria:
        rows = _query(
            "SELECT * FROM bets WHERE account_id = ? AND loteria = ? "
            "ORDER BY concurso DESC, criado_em DESC",
            (account_id, loteria),
        )
    else:
        rows = _query(
            "SELECT * FROM bets WHERE account_id = ? ORDER BY concurso DESC, criado_em DESC",
            (account_id,),
        )
    for r in rows:
        r["dezenas"] = json.loads(r["dezenas"])
        r.setdefault("loteria", "mega")
        esp = r.get("espalhar")
        r["espalhar"] = None if esp is None else bool(esp)
        r["espalhar_deduzido"] = None if esp is None else bool(r.get("espalhar_deduzido"))
    return rows


def upsert_bet(account_id: str, bet: dict) -> None:
    _write([(_BET_INSERT, _bet_params(account_id, bet))])


def upsert_bets(account_id: str, bets: list[dict]) -> int:
    statements = [(_BET_INSERT, _bet_params(account_id, bet)) for bet in bets]
    if statements:
        _write(statements)
    return len(statements)


def delete_bet(account_id: str, bet_id: str) -> None:
    _write([("DELETE FROM bets WHERE account_id = ? AND id = ?", (account_id, bet_id))])
