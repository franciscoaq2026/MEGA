from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Mega-Sena Stats API", version="0.1.0")

# Em desenvolvimento o frontend roda em outra porta (Vite, 5173).
# O proxy do Vite já encaminha /api, mas o CORS permite também acesso direto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": "megasena-stats",
        "version": app.version,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# As rotas ficam disponíveis em /api/... (uso normal) e também sem o prefixo,
# porque algumas plataformas (ex.: Vercel multi-service) removem o /api ao
# encaminhar a requisição para o serviço.
app.include_router(router, prefix="/api")
app.include_router(router, include_in_schema=False)
