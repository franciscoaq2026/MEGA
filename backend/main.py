# Ponto de entrada para deploy (Vercel e afins detectam main.py na raiz do serviço).
# Em desenvolvimento local, use: uvicorn app.main:app --reload
from app.main import app  # noqa: F401
