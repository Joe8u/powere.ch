#apps/api/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import os

from .core import EMBED_BACKEND, EMBED_DIM, QDRANT_COLLECTION, CHAT_MODEL, chat_client
from app.routers.ai_guide_router import router as ai_router
from app.routers import warehouse

DEFAULT_ORIGINS = "https://www.powere.ch,https://powere.ch,http://localhost:4321"
CORS_ORIGINS = [o.strip() for o in os.getenv("API_CORS_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]
ROOT_PATH = os.getenv("API_ROOT_PATH", "")  # z.B. "/api"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("API_ALLOWED_HOSTS", "localhost,127.0.0.1,powere.ch,www.powere.ch").split(",")]

app = FastAPI(
    title="powere.ch API",
    version="0.2.0",
    default_response_class=JSONResponse,
    root_path=ROOT_PATH if ROOT_PATH else "",   # <- Pylance happy
)

# optional, aber nützlich in Prod
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "backend": EMBED_BACKEND,
        "dim": EMBED_DIM,
        "collection": QDRANT_COLLECTION,
        "chat_model": CHAT_MODEL if chat_client else None,
    }

@app.get("/readyz")
def readyz():
    return {"ready": True, "qdrant_configured": bool(QDRANT_COLLECTION), "chat_client": bool(chat_client)}

@app.get("/health", include_in_schema=False)
def health_alias():
    return healthz()

@app.get("/v1/ping")
def ping():
    return {"msg": "pong"}

app.include_router(ai_router, tags=["ai-guide"])
