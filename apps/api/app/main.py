from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
client: OpenAI = OpenAI()
#/Users/jonathan/Library/Mobile Documents/com~apple~CloudDocs/Documents/GitHub/powere.ch/apps/api/app/main.py
from app.lib.openai_wrap import chat_completion
import os
import uuid
import logging
import re
import time
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, Body, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
try:
    from fastapi.responses import ORJSONResponse as _DefaultResponse
    _DEFAULT_RESPONSE = _DefaultResponse
except Exception:
    from fastapi.responses import JSONResponse as _DefaultResponse  # fallback ohne orjson
    _DEFAULT_RESPONSE = _DefaultResponse
from pydantic import BaseModel, Field

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels



# ---- Config ----
BACKEND = os.getenv("EMBED_BACKEND", "openai").lower()  # "openai" | "fastembed"
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_docs")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "15"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
OPENAI_BACKOFF_BASE = float(os.getenv("OPENAI_BACKOFF_BASE", "0.5"))

# Ingest chunking
INGEST_MAX_CHARS = int(os.getenv("INGEST_MAX_CHARS", "2000"))
INGEST_OVERLAP = int(os.getenv("INGEST_OVERLAP", "200"))

# ---- Embeddings (two backends) ----
if BACKEND == "fastembed":
    from fastembed import TextEmbedding  # type: ignore
    FASTEMBED_MODEL = os.getenv("FASTEMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embedder = TextEmbedding(model_name=FASTEMBED_MODEL)
    EMBED_DIM = 384

    def embed_batch(texts: List[str]) -> List[List[float]]:
        return [list(vec) for vec in embedder.embed(texts)]
else:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set (and EMBED_BACKEND!=fastembed)")
    from openai import OpenAI
    openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT_SECONDS)
    EMBED_DIM = 1536

    def embed_batch(texts: List[str]) -> List[List[float]]:
        last_err: Optional[Exception] = None
        for attempt in range(1, OPENAI_MAX_RETRIES + 1):
            try:
                resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
                return [d.embedding for d in resp.data]
            except Exception as e:
                last_err = e
                time.sleep(min(OPENAI_BACKOFF_BASE * (2 ** (attempt - 1)), 4.0))
        assert last_err is not None
        raise last_err

# ---- Chat client (optional; required for /v1/chat) ----
chat_client = None
if OPENAI_API_KEY:
    from openai import OpenAI as _ChatOpenAI  # type: ignore
    chat_client = _ChatOpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT_SECONDS)

    def _chat_complete(messages: list[ChatCompletionMessageParam]):
        last_err: Optional[Exception] = None
        for attempt in range(1, OPENAI_MAX_RETRIES + 1):
            try:
                return chat_client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=messages,
                    temperature=0.0,
                )
            except Exception as e:
                last_err = e
                time.sleep(min(OPENAI_BACKOFF_BASE * (2 ** (attempt - 1)), 4.0))
        assert last_err is not None
        raise last_err

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

def normalize_point_id(raw: Optional[str]) -> str:
    """Always return a string ID for Qdrant."""
    if raw is None:
        return str(uuid.uuid4())
    if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
        return str(int(raw))
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(uuid.uuid4())

def stable_uuid_for_doc(d: "IngestDoc") -> str:
    basis = f"{d.url or ''}|{d.title or ''}|{d.content}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, basis))

def chunk_text(text: str, max_chars: int = INGEST_MAX_CHARS, overlap: int = INGEST_OVERLAP) -> List[str]:
    """Paragraph-aware chunking with overlap for long paragraphs."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    paras = re.split(r"\n{2,}", text)
    chunks: List[str] = []
    cur = ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 2 <= max_chars:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                chunks.append(cur)
            while len(p) > max_chars:
                head = p[:max_chars]
                chunks.append(head)
                p = p[max_chars - overlap :]
            cur = p
    if cur:
        chunks.append(cur)
    return chunks

# ---- FastAPI ----
app = FastAPI(title="powere.ch API", version="0.2.0", default_response_class=_DEFAULT_RESPONSE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.powere.ch", "https://powere.ch", "http://localhost:4321"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional: Prometheus metrics at /metrics if package is installed
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore
    Instrumentator().instrument(app).expose(app)
except Exception:
    logging.info("Prometheus metrics disabled (package missing)")

class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2)
    top_k: int = Field(5, ge=1, le=20)

@app.get("/healthz")
def health():
    info: Dict[str, Any] = {
        "status": "ok",
        "backend": BACKEND,
        "dim": EMBED_DIM,
        "collection": QDRANT_COLLECTION,
        "chat_model": CHAT_MODEL if chat_client else None,
    }
    try:
        ensure_collection()
        try:
            res = qdrant.count(collection_name=QDRANT_COLLECTION, exact=False)  # type: ignore
            points = getattr(res, "count", None) or getattr(res, "points_count", None)
            if points is not None:
                info["points"] = int(points)
        except Exception:
            pass
    except Exception as e:
        info["qdrant_error"] = str(e)
    return info

@app.post("/v1/ingest")
def ingest(docs: List[IngestDoc] = Body(..., min_items=1)):
    ensure_collection()

    pending: List[Dict[str, Any]] = []
    for d in docs:
        parts = chunk_text(d.content)
        total = len(parts)
        if total == 0:
            continue
        base_id = normalize_point_id(d.id) if d.id is not None else stable_uuid_for_doc(d)
        for idx, part in enumerate(parts):
            pending.append({
                "point_id": base_id if total == 1 else f"{base_id}::c{idx:04d}",
                "title": d.title,
                "url": d.url,
                "content": part,
                "chunk_index": idx,
                "chunk_total": total,
            })

    if not pending:
        raise HTTPException(status_code=400, detail="no_content")

    try:
        vectors = embed_batch([p["content"] for p in pending])
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    try:
        points = []
        for p, vec in zip(pending, vectors):
            payload = {
                "title": p["title"],
                "url": p["url"],
                "content": p["content"],
                "chunk_index": p["chunk_index"],
                "chunk_total": p["chunk_total"],
            }
            points.append(qmodels.PointStruct(id=p["point_id"], vector=vec, payload=payload))
        qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
    except Exception as e:
        logging.exception("qdrant_upsert_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_upsert_failed: {e}")

    return {"received_docs": len(docs), "upserted_chunks": len(pending), "collection": QDRANT_COLLECTION}

@app.get("/v1/search")
def search(q: str = Query(..., min_length=2), top_k: int = Query(5, ge=1, le=20)) -> Dict[str, Any]:
    ensure_collection()
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="empty_query")

    try:
        query_vec = embed_batch([query])[0]
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
            "id": str(h.id),
            "score": h.score,
            "title": payload.get("title"),
            "url": payload.get("url"),
            "snippet": (payload.get("content") or "")[:320],
            "chunk_index": payload.get("chunk_index"),
            "chunk_total": payload.get("chunk_total"),
        })
    return {"query": query, "results": results}

@app.post("/v1/chat")
def chat(req: ChatRequest):
    if not chat_client:
        raise HTTPException(status_code=500, detail="chat_backend_not_configured: set OPENAI_API_KEY")

    ensure_collection()

    try:
        query_vec = embed_batch([req.question])[0]
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

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
        citations.append({
            "n": i,
            "id": str(h.id),
            "title": title,
            "url": url,
            "score": h.score,
            "chunk_index": payload.get("chunk_index"),
            "chunk_total": payload.get("chunk_total"),
        })

    system_msg = (
        "Du bist der AI-Guide von powere.ch. Beantworte Fragen NUR mit Hilfe des Kontexts. "
        "Wenn der Kontext etwas nicht enthält, sage ehrlich, dass du es nicht weißt. "
        "Fasse dich kurz und füge Quellenhinweise wie [1], [2] ein, wenn relevant."
    )
    user_msg = (f"Frage: {req.question}\n\nKontext:\n" + "\n\n".join(contexts)) if contexts else (
        f"Frage: {req.question}\n\nKontext: (leer)"
    )

    try:
        completion = _chat_complete(
            [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        logging.exception("chat_failed")
        raise HTTPException(status_code=502, detail=f"chat_failed: {e}")

    return {"answer": answer, "citations": citations, "used_model": CHAT_MODEL}

