from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import List, Optional
import os, json, yaml
from pathlib import Path

# ---- Pfade (Repo-Root → ai_guide)
REPO_ROOT = Path(__file__).resolve().parents[3]
AI_GUIDE = REPO_ROOT / "ai_guide"
POLICY = AI_GUIDE / "config" / "policy.yaml"
STEPS_MANIFEST = AI_GUIDE / "manifests" / "steps_manifest.json"
KB_DIR = AI_GUIDE / "kb"

# ---- Embeddings / Qdrant (fastembed default)
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "fastembed").lower()
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_docs")

# Lazy init singletons
_qdrant_client = None
_embedder = None
_embed_dim = None

def get_embedder():
    global _embedder, _embed_dim
    if _embedder is not None:
        return _embedder, _embed_dim

    if EMBED_BACKEND == "openai":
        try:
            from openai import OpenAI
            model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            def _emb(texts: List[str]):
                # kleine Batches zur Sicherheit
                out = []
                for t in texts:
                    e = client.embeddings.create(model=model, input=t)
                    out.append(e.data[0].embedding)
                return out
            # Dimension aus Dummy
            dim = len(_emb(["probe"])[0])
            _embedder = _emb
            _embed_dim = dim
        except Exception as e:
            raise RuntimeError(f"openai backend init failed: {e}")
    else:
        # fastembed (lokal, keine Keys)
        try:
            from fastembed.embedding import TextEmbedding
            model_name = os.getenv("FASTEMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            te = TextEmbedding(model_name=model_name)
            # Dimension per Probe
            dim = len(next(te.embed(["probe"])))
            def _emb(texts: List[str]):
                return list(te.embed(texts))
            _embedder = _emb
            _embed_dim = dim
        except Exception as e:
            raise RuntimeError(f"fastembed init failed: {e}")

    return _embedder, _embed_dim

def get_qdrant():
    global _qdrant_client, _embed_dim
    if _qdrant_client is not None:
        return _qdrant_client
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import VectorParams, Distance
    client = QdrantClient(url=QDRANT_URL)
    # Collection sicherstellen (nicht neu erstellen, wenn vorhanden)
    try:
        client.get_collection(QDRANT_COLLECTION)
    except Exception:
        _, dim = get_embedder()
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )
    _qdrant_client = client
    return _qdrant_client

# ---- FastAPI
app = FastAPI(title="powere.ch API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.powere.ch", "https://powere.ch", "http://localhost:4321"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def health():
    try:
        emb, dim = get_embedder()
        _ = get_qdrant()
        return {"status": "ok", "backend": EMBED_BACKEND, "dim": dim, "collection": QDRANT_COLLECTION}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}

@app.get("/v1/ping")
def ping():
    return {"msg": "pong"}

# ---- ai_guide: Config / Manifeste / KB

@app.get("/v1/ai-guide/config", response_model=dict)
def ai_config():
    if not POLICY.exists():
        raise HTTPException(404, "policy.yaml not found")
    return yaml.safe_load(POLICY.read_text(encoding="utf-8"))

@app.get("/v1/ai-guide/steps", response_model=list)
def ai_steps():
    if not STEPS_MANIFEST.exists():
        raise HTTPException(404, "steps_manifest.json not found")
    return json.loads(STEPS_MANIFEST.read_text(encoding="utf-8"))

@app.get("/v1/ai-guide/kb/overview", response_class=PlainTextResponse)
def ai_kb_overview():
    p = KB_DIR / "steps_overview.md"
    if not p.exists():
        raise HTTPException(404, "steps_overview.md not found")
    return p.read_text(encoding="utf-8")

@app.get("/v1/ai-guide/kb/{path:path}", response_class=PlainTextResponse)
def ai_kb_any(path: str):
    p = KB_DIR / path
    if not p.exists():
        raise HTTPException(404, f"{path} not found")
    return p.read_text(encoding="utf-8")

# ---- RAG: ingest / search (Qdrant + Embeddings)

class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str

@app.post("/v1/ingest", response_model=dict)
def ingest(docs: List[IngestDoc]):
    emb, _ = get_embedder()
    client = get_qdrant()
    from uuid import uuid4
    vectors = emb([d.content for d in docs])
    points = []
    for d, v in zip(docs, vectors):
        pid = d.id or str(uuid4())
        payload = {"title": d.title, "url": d.url, "content": d.content}
        points.append({"id": pid, "vector": v, "payload": payload})
    try:
        client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    except Exception as e:
        raise HTTPException(500, f"qdrant_upsert_failed: {e}")
    return {"received": len(points), "collection": QDRANT_COLLECTION}

@app.get("/v1/search", response_model=dict)
def search(q: str = Query(..., min_length=1), top_k: int = 5):
    emb, _ = get_embedder()
    client = get_qdrant()
    try:
        qvec = emb([q])[0]
        hits = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=qvec,
            limit=max(1, min(50, top_k))
        )
    except Exception as e:
        raise HTTPException(500, f"search_failed: {e}")

    results = []
    for h in hits:
        payload = h.payload or {}
        results.append({
            "id": str(h.id),
            "score": float(h.score),
            "title": payload.get("title"),
            "url": payload.get("url"),
            "snippet": (payload.get("content") or "")[:400]
        })
    return {"query": q, "results": results}