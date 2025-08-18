from __future__ import annotations

from fastapi import FastAPI, Body, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from typing import List, Optional, Any
import os, uuid, logging

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
from openai import OpenAI  # ist installiert laut requirements

# -----------------------------------------------------------------------------
# Konfiguration
# -----------------------------------------------------------------------------
BACKEND = os.getenv("EMBED_BACKEND", "openai").lower()  # "openai" | "fastembed"
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_docs")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

logging.basicConfig(level=logging.INFO)

# -----------------------------------------------------------------------------
# Embeddings (zwei Backends)
# -----------------------------------------------------------------------------
if BACKEND == "fastembed":
    # Lokale, freie Embeddings (nur wenn Paket installiert ist)
    try:
        from fastembed import TextEmbedding  # optional dependency
    except Exception as e:
        raise RuntimeError(f"EMBED_BACKEND=fastembed, aber fastembed ist nicht installiert: {e}")

    FASTEMBED_MODEL = os.getenv("FASTEMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    _embedder = TextEmbedding(model_name=FASTEMBED_MODEL)
    EMBED_DIM = 384

    def embed_batch(texts: List[str]) -> List[List[float]]:
        # fastembed liefert Iterator -> in Listen wandeln
        return [list(vec) for vec in _embedder.embed(texts)]
else:
    # OpenAI Embeddings
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt (und EMBED_BACKEND!=fastembed)")
    _openai = OpenAI(api_key=OPENAI_API_KEY)
    EMBED_DIM = 1536

    def embed_batch(texts: List[str]) -> List[List[float]]:
        resp = _openai.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [d.embedding for d in resp.data]

# Chat-Client (für /v1/chat)
chat_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# -----------------------------------------------------------------------------
# Qdrant
# -----------------------------------------------------------------------------
qdrant = QdrantClient(url=QDRANT_URL)

def ensure_collection() -> None:
    try:
        qdrant.get_collection(QDRANT_COLLECTION)
    except Exception:
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

def normalize_point_id(raw: Optional[str]) -> Any:
    """
    Rückgabe einer Qdrant-kompatiblen ID (int oder UUID-String).
    Ungültige Werte -> neue UUID.
    """
    if raw is None:
        return str(uuid.uuid4())
    if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
        return int(raw)
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(uuid.uuid4())

def stable_uuid_for(d: "IngestDoc") -> str:
    """
    Stabile UUID auf Basis (url|title|content) – macht Ingest idempotent,
    wenn keine explizite id übergeben wird.
    """
    basis = f"{d.url or ''}|{d.title or ''}|{d.content}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, basis))

# -----------------------------------------------------------------------------
# FastAPI
# -----------------------------------------------------------------------------
app = FastAPI(
    title="powere.ch API",
    version="0.2.0",
    default_response_class=JSONResponse,  # wichtig: kein orjson nötig
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.powere.ch",
        "https://powere.ch",
        "http://localhost:4321",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str

class ChatRequest(BaseModel):
    question: str
    top_k: int = 5

# -----------------------------------------------------------------------------
# Health / Ping
# -----------------------------------------------------------------------------
@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "backend": BACKEND,
        "dim": EMBED_DIM,
        "collection": QDRANT_COLLECTION,
        "chat_model": CHAT_MODEL if chat_client else None,
    }

# compose healthcheck erwartet /health
@app.get("/health", include_in_schema=False)
def health_alias():
    return healthz()

@app.get("/v1/ping")
def ping():
    return {"msg": "pong"}

# -----------------------------------------------------------------------------
# RAG: Ingest
# -----------------------------------------------------------------------------
@app.post("/v1/ingest")
def ingest(docs: List[IngestDoc] = Body(..., min_items=1)):
    ensure_collection()
    try:
        vectors = embed_batch([d.content for d in docs])
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    points: list[PointStruct] = []
    for d, vec in zip(docs, vectors):
        pid = normalize_point_id(d.id) if d.id is not None else stable_uuid_for(d)
        payload = {"title": d.title, "url": d.url, "content": d.content}
        points.append(PointStruct(id=pid, vector=vec, payload=payload))

    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)

    try:
        qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
    except Exception as e:
        logging.exception("qdrant_upsert_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_upsert_failed: {e}")

    return {"received": len(docs), "collection": QDRANT_COLLECTION}

# -----------------------------------------------------------------------------
# RAG: Search
# -----------------------------------------------------------------------------
@app.get("/v1/search")
def search(q: str = Query(..., min_length=2), top_k: int = 5) -> dict[str, Any]:
    try:
        query_vec = embed_batch([q])[0]
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    try:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logging.exception("qdrant_search_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_search_failed: {e}")

    results = []
    for h in hits:
        payload = h.payload or {}
        results.append(
            {
                "id": h.id,
                "score": h.score,
                "title": payload.get("title"),
                "url": payload.get("url"),
                "snippet": (payload.get("content") or "")[:240],
            }
        )
    return {"query": q, "results": results}

# -----------------------------------------------------------------------------
# RAG: Chat (mit Zitationen)
# -----------------------------------------------------------------------------
@app.post("/v1/chat")
def chat(req: ChatRequest):
    if not chat_client:
        raise HTTPException(status_code=500, detail="chat_backend_not_configured: set OPENAI_API_KEY")

    # 1) embed Frage
    try:
        query_vec = embed_batch([req.question])[0]
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    # 2) retrieve
    try:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            limit=req.top_k,
            with_payload=True,
        )
    except Exception as e:
        logging.exception("qdrant_search_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_search_failed: {e}")

    contexts: List[str] = []
    citations: List[dict[str, Any]] = []
    for i, h in enumerate(hits, start=1):
        payload = h.payload or {}
        title = payload.get("title") or f"Doc {i}"
        url = payload.get("url")
        content = payload.get("content") or ""
        contexts.append(f"[{i}] {title}\n{content}")
        citations.append({"id": str(h.id), "title": title, "url": url, "score": h.score})

    system_msg = (
        "Du bist der AI-Guide von powere.ch. Beantworte Fragen NUR mit Hilfe des Kontexts. "
        "Wenn der Kontext etwas nicht enthält, sage ehrlich, dass du es nicht weißt. "
        "Fasse dich kurz und füge Quellenhinweise wie [1], [2] ein, wenn relevant."
    )
    user_msg = (
        f"Frage: {req.question}\n\nKontext:\n" + "\n\n".join(contexts)
        if contexts
        else f"Frage: {req.question}\n\nKontext: (leer)"
    )

    try:
        completion = chat_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        logging.exception("chat_failed")
        raise HTTPException(status_code=502, detail=f"chat_failed: {e}")

    return {"answer": answer, "citations": citations, "used_model": CHAT_MODEL}