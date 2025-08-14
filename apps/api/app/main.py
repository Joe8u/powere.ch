from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os, uuid, logging

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

app = FastAPI(title="powere.ch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.powere.ch", "https://powere.ch", "http://localhost:4321"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- ENV
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Use default OpenAI endpoint; only set BASE_URL if you truly use a compatible provider.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_docs")
EMBED_DIM = 1536  # text-embedding-3-small / large

# ---- Clients
if not OPENAI_API_KEY:
    # Fail early with a clear message
    raise RuntimeError("OPENAI_API_KEY is not set")
openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL)

def ensure_collection():
    try:
        qdrant.get_collection(QDRANT_COLLECTION)
    except Exception:
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=EMBED_DIM, distance=qmodels.Distance.COSINE),
        )

class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str

@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.get("/v1/ping")
def ping():
    return {"msg": "pong"}

@app.post("/v1/ingest")
def ingest(docs: List[IngestDoc] = Body(..., min_items=1)):
    ensure_collection()

    inputs = [d.content for d in docs]
    try:
        emb = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)
    except Exception as e:
        # Surface the real cause with a proper status code
        # Typical: 401 Unauthorized (bad key) or 429 (quota) – but we use 502 as generic upstream failure.
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    points = []
    try:
        for d, e in zip(docs, emb.data):
            pid = d.id or str(uuid.uuid4())
            payload = {"title": d.title, "url": d.url, "content": d.content}
            points.append(qmodels.PointStruct(id=pid, vector=e.embedding, payload=payload))

        qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
    except Exception as e:
        logging.exception("qdrant_upsert_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_upsert_failed: {e}")

    return {"received": len(points), "collection": QDRANT_COLLECTION}