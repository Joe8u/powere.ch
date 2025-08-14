from fastapi import FastAPI, Body, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
import os, uuid, logging

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# ---- Config ----
BACKEND = os.getenv("EMBED_BACKEND", "openai").lower()  # "openai" | "fastembed"
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_docs")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

# ---- Embeddings (two backends) ----
if BACKEND == "fastembed":
    # Local, free embeddings
    from fastembed import TextEmbedding

    FASTEMBED_MODEL = os.getenv("FASTEMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embedder = TextEmbedding(model_name=FASTEMBED_MODEL)
    EMBED_DIM = 384

    def embed_batch(texts: List[str]) -> List[List[float]]:
        # fastembed returns an iterator of vectors -> normalize to plain lists
        return [list(vec) for vec in embedder.embed(texts)]
else:
    # OpenAI embeddings
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set (and EMBED_BACKEND!=fastembed)")
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    EMBED_DIM = 1536

    def embed_batch(texts: List[str]) -> List[List[float]]:
        resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [d.embedding for d in resp.data]

# ---- Chat client (optional; required for /v1/chat) ----
chat_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ---- Qdrant ----
qdrant = QdrantClient(url=QDRANT_URL)


def ensure_collection():
    try:
        qdrant.get_collection(QDRANT_COLLECTION)
    except Exception:
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=EMBED_DIM, distance=qmodels.Distance.COSINE),
        )


def normalize_point_id(raw: Optional[str]) -> Any:
    """Return a Qdrant-acceptable ID (int or UUID string).
    If the provided value is not valid, generate a fresh UUID string.
    """
    if raw is None:
        return str(uuid.uuid4())
    # int-like
    if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
        return int(raw)
    # UUID-like
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(uuid.uuid4())


# ---- FastAPI ----
app = FastAPI(title="powere.ch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.powere.ch", "https://powere.ch", "http://localhost:4321"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str


class ChatRequest(BaseModel):
    question: str
    top_k: int = 5


@app.get("/healthz")
def health():
    return {
        "status": "ok",
        "backend": BACKEND,
        "dim": EMBED_DIM,
        "collection": QDRANT_COLLECTION,
        "chat_model": CHAT_MODEL if chat_client else None,
    }


@app.post("/v1/ingest")
def ingest(docs: List[IngestDoc] = Body(..., min_items=1)):
    ensure_collection()
    inputs = [d.content for d in docs]

    try:
        vectors = embed_batch(inputs)
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    try:
        points = []
        for d, vec in zip(docs, vectors):
            pid = normalize_point_id(d.id)
            payload = {"title": d.title, "url": d.url, "content": d.content}
            points.append(qmodels.PointStruct(id=pid, vector=vec, payload=payload))
        qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
    except Exception as e:
        logging.exception("qdrant_upsert_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_upsert_failed: {e}")

    return {"received": len(docs), "collection": QDRANT_COLLECTION}


@app.get("/v1/search")
def search(q: str = Query(..., min_length=2), top_k: int = 5) -> dict[str, Any]:
    # Embed query with the same backend as ingest
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
        results.append({
            "id": h.id,
            "score": h.score,
            "title": payload.get("title"),
            "url": payload.get("url"),
            "snippet": (payload.get("content") or "")[:240],
        })
    return {"query": q, "results": results}


@app.post("/v1/chat")
def chat(req: ChatRequest):
    if not chat_client:
        raise HTTPException(status_code=500, detail="chat_backend_not_configured: set OPENAI_API_KEY")

    # Embed user question
    try:
        query_vec = embed_batch([req.question])[0]
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    # Retrieve top_k docs
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

    contexts = []
    citations = []
    for i, h in enumerate(hits, start=1):
        payload = h.payload or {}
        title = payload.get("title") or f"Doc {i}"
        url = payload.get("url")
        content = payload.get("content") or ""
        contexts.append(f"[{i}] {title}\n{content}")
        citations.append({"id": str(h.id), "title": title, "url": url, "score": h.score})

    system_msg = (
        "Du bist der AI‑Guide von powere.ch. Beantworte Fragen NUR mit Hilfe des Kontexts. "
        "Wenn der Kontext etwas nicht enthält, sage ehrlich, dass du es nicht weißt. "
        "Fasse dich kurz und füge Quellenhinweise wie [1], [2] ein, wenn relevant."
    )
    user_msg = (
        f"Frage: {req.question}\n\nKontext:\n" + "\n\n".join(contexts)
        if contexts else f"Frage: {req.question}\n\nKontext: (leer)"
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