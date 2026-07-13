from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers.draws import router as draws_router
from .routers.games import router as games_router
from .routers.stats import router as stats_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mega-Sena Stats API", version="0.2.0", lifespan=lifespan)

# Em desenvolvimento o frontend roda em outra porta (Vite, 5173).
# O proxy do Vite já encaminha /api, mas o CORS permite também acesso direto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter()
api.include_router(draws_router)
api.include_router(games_router)
api.include_router(stats_router)


@api.get("/health")
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
app.include_router(api, prefix="/api")
app.include_router(api, include_in_schema=False)
