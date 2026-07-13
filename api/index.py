"""Ponto de entrada do backend no Vercel (Python Serverless Function).

O Vercel serve qualquer arquivo em /api como função. Este expõe o app
FastAPI (ASGI) inteiro; o vercel.json encaminha /api/* para cá.
"""

import os
import sys

# Torna o pacote backend/ importável a partir desta função.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

# Em serverless o startup do ASGI nem sempre roda; garantimos o schema aqui,
# uma vez por cold start (CREATE TABLE IF NOT EXISTS é idempotente).
try:
    init_db()
except Exception as exc:  # noqa: BLE001 - não derruba a função por falha de init
    print(f"[init_db] aviso: {exc}", file=sys.stderr)

# O Vercel procura por uma variável ASGI/WSGI chamada `app`.
__all__ = ["app"]
