"""Popula o banco Turso com o histórico completo de sorteios — de uma vez.

Rode este script UMA vez, da sua máquina (que alcança a API da Caixa e o
Turso), para evitar os limites de tempo das funções serverless do Vercel.
Depois disso, o app em produção só busca os concursos novos.

Uso:
    export TURSO_DATABASE_URL="libsql://seu-banco.turso.io"
    export TURSO_AUTH_TOKEN="seu-token"

    # opção A — baixar tudo da API da Caixa (com fallback):
    python seed_turso.py

    # opção B — carregar de um CSV (concurso,data,dezena1..dezena6):
    python seed_turso.py caminho/para/megasena.csv
"""

import asyncio
import os
import sys


async def main() -> None:
    if not os.environ.get("TURSO_DATABASE_URL"):
        sys.exit("Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN antes de rodar.")

    # Importa depois de conferir o env (db.py decide o backend na importação).
    from app import db
    from app.fetcher import fetch_latest, fetch_many

    print(f"Banco: {db.backend_name()}  ({os.environ['TURSO_DATABASE_URL']})")
    db.init_db()

    if len(sys.argv) > 1:  # opção B: CSV
        from app.csv_utils import parse_draws_csv

        path = sys.argv[1]
        rows, errors = parse_draws_csv(open(path, encoding="utf-8-sig").read())
        db.upsert_draws(rows)
        print(f"Importados {len(rows)} sorteios do CSV ({len(errors)} ignorados).")
        return

    # opção A: API da Caixa
    latest = await fetch_latest()
    db.upsert_draws([latest])
    db.set_meta("proximo", latest["proximo"])
    print(f"Último concurso remoto: {latest['concurso']}")

    existentes = db.all_concursos()
    faltando = [n for n in range(1, latest["concurso"]) if n not in existentes]
    print(f"Faltam {len(faltando)} concursos — baixando…")

    lote = 200
    for i in range(0, len(faltando), lote):
        parte = faltando[i : i + lote]
        obtidos, erros = await fetch_many(parte)
        db.upsert_draws(obtidos)
        print(
            f"  {min(i + lote, len(faltando))}/{len(faltando)} "
            f"(+{len(obtidos)}, {len(erros)} falhas)"
        )

    print(f"Pronto. Total no banco: {db.count_draws()} sorteios.")


if __name__ == "__main__":
    asyncio.run(main())
