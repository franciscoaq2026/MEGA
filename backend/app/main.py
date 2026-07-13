from datetime import datetime, timezone

from fastapi import FastAPI
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


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "megasena-stats",
        "version": app.version,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
