from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os, uuid

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

# ---- Konfiguration aus ENV ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_docs")

# Dimension 1536 passt für text-embedding-3-small/large (und ada-002)
EMBED_DIM = 1536

# ---- Clients initialisieren ----
openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
qdrant = QdrantClient(url=QDRANT_URL)

# Collection sicherstellen
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

    # Embeddings holen (batch)
    inputs = [d.content for d in docs]
    emb = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)

    # Punkte bauen
    points = []
    for d, e in zip(docs, emb.data):
        pid = d.id or str(uuid.uuid4())
        payload = {"title": d.title, "url": d.url, "content": d.content}
        points.append(qmodels.PointStruct(id=pid, vector=e.embedding, payload=payload))

    # Upsert nach Qdrant
    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)

    return {"received": len(points), "collection": QDRANT_COLLECTION}