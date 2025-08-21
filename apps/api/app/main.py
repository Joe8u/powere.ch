from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core import EMBED_BACKEND, EMBED_DIM, QDRANT_COLLECTION, CHAT_MODEL, chat_client
from .routers.rag import router as rag_router

app = FastAPI(
    title="powere.ch API",
    version="0.2.0",
    default_response_class=JSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.powere.ch", "https://powere.ch", "http://localhost:4321"],
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

@app.get("/health", include_in_schema=False)
def health_alias():
    return healthz()

@app.get("/v1/ping")
def ping():
    return {"msg": "pong"}

# Router registrieren
app.include_router(rag_router)