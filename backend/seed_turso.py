"""Popula o banco Turso com o histórico completo de sorteios — de uma vez.

Rode este script UMA vez, da sua máquina (que alcança a API da Caixa e o
Turso), para evitar os limites de tempo das funções serverless do Vercel.
Depois disso, o app em produção só busca os concursos novos.

Uso:
    export TURSO_DATABASE_URL="libsql://seu-banco.turso.io"
    export TURSO_AUTH_TOKEN="seu-token"

    # todas as loterias, a partir do histórico embutido no repositório
    # (instantâneo, sem rede) e completando o que falta pela API:
    python seed_turso.py

    # só uma loteria:
    python seed_turso.py --loteria lofa

    # carregar de um CSV (concurso,data,dezena1..dezenaN):
    python seed_turso.py --loteria mega caminho/para/megasena.csv
"""

import asyncio
import os
import sys


def _args() -> tuple[list[str], str | None]:
    """Devolve (loterias, caminho_csv) a partir da linha de comando."""
    from app import lotteries

    argv = sys.argv[1:]
    loteria = None
    if "--loteria" in argv:
        i = argv.index("--loteria")
        loteria = argv[i + 1] if i + 1 < len(argv) else None
        del argv[i : i + 2]
        if not lotteries.is_valid(loteria):
            sys.exit(f"Loteria inválida: {loteria!r}. Use uma de: {list(lotteries.LOTERIAS)}")
    codes = [loteria] if loteria else list(lotteries.LOTERIAS)
    return codes, (argv[0] if argv else None)


async def semear(code: str) -> None:
    from app import db, lotteries
    from app.fetcher import FetchError, fetch_latest, fetch_many

    cfg = lotteries.get_loteria(code)
    print(f"\n=== {cfg['nome']} ({code}) ===")

    # 1) histórico embutido: instantâneo e sem depender de rede
    seed = db.load_bundled_seed(code)
    if seed:
        novos = [s for s in seed if s["concurso"] not in db.concursos_com_data(code)]
        if novos:
            db.upsert_draws(novos, code)
        print(f"Seed embutido: {len(seed)} concursos ({len(novos)} novos no banco).")

    # 2) completa com o que for mais novo que o seed
    try:
        latest = await fetch_latest(code)
    except FetchError as e:
        print(f"APIs indisponíveis ({e}); ficou só com o seed embutido.")
        print(f"Total no banco: {db.count_draws(code)} sorteios.")
        return

    db.upsert_draws([latest], code)
    prox_key = "proximo" if code == "mega" else f"proximo:{code}"
    db.set_meta(prox_key, latest["proximo"])
    print(f"Último concurso remoto: {latest['concurso']}")

    existentes = db.concursos_com_data(code)
    faltando = [n for n in range(1, latest["concurso"]) if n not in existentes]
    if not faltando:
        print(f"Nada a baixar. Total no banco: {db.count_draws(code)} sorteios.")
        return
    print(f"Faltam {len(faltando)} concursos — baixando…")

    lote = 200
    for i in range(0, len(faltando), lote):
        parte = faltando[i : i + lote]
        obtidos, erros = await fetch_many(parte, code)
        db.upsert_draws(obtidos, code)
        print(
            f"  {min(i + lote, len(faltando))}/{len(faltando)} "
            f"(+{len(obtidos)}, {len(erros)} falhas)"
        )

    print(f"Pronto. Total no banco: {db.count_draws(code)} sorteios.")


async def main() -> None:
    if not os.environ.get("TURSO_DATABASE_URL"):
        sys.exit("Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN antes de rodar.")

    # Importa depois de conferir o env (db.py decide o backend na importação).
    from app import db

    codes, csv_path = _args()
    print(f"Banco: {db.backend_name()}  ({os.environ['TURSO_DATABASE_URL']})")
    db.init_db()

    if csv_path:
        from app.csv_utils import parse_draws_csv

        if len(codes) > 1:
            sys.exit("Com CSV, informe a loteria: python seed_turso.py --loteria mega arquivo.csv")
        rows, errors = parse_draws_csv(
            open(csv_path, encoding="utf-8-sig").read(), codes[0]
        )
        db.upsert_draws(rows, codes[0])
        print(f"Importados {len(rows)} sorteios do CSV ({len(errors)} ignorados).")
        return

    for code in codes:
        await semear(code)


if __name__ == "__main__":
    asyncio.run(main())
