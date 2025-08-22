from __future__ import annotations

import os, uuid, logging
from typing import Any, Optional, List

from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

# --------- ENV / Config ---------
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "openai").lower()  # "openai" | "fastembed"
BACKEND = EMBED_BACKEND  # Alias, falls irgendwo noch BACKEND verwendet wird

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_docs")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

# --------- Embeddings ---------
if EMBED_BACKEND == "fastembed":
    try:
        from fastembed import TextEmbedding  # optional dependency
    except Exception as e:
        raise RuntimeError(f"EMBED_BACKEND=fastembed, aber fastembed nicht installiert: {e}")
    _embedder = TextEmbedding(model_name=os.getenv("FASTEMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    EMBED_DIM = 384

    def embed_batch(texts: List[str]) -> List[List[float]]:
        return [list(vec) for vec in _embedder.embed(texts)]
else:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt (und EMBED_BACKEND!=fastembed)")
    _openai = OpenAI(api_key=OPENAI_API_KEY)
    EMBED_DIM = 1536

    def embed_batch(texts: List[str]) -> List[List[float]]:
        resp = _openai.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [d.embedding for d in resp.data]

# --------- Chat-Client ---------
chat_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# --------- Qdrant ---------
qdrant = QdrantClient(url=QDRANT_URL)

def ensure_collection() -> None:
    try:
        qdrant.get_collection(QDRANT_COLLECTION)
    except Exception:
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

# --------- Utils ---------
def normalize_point_id(raw: Optional[str]) -> Any:
    if raw is None:
        return str(uuid.uuid4())
    if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
        return int(raw)
    try:
        return str(uuid.UUID(str(raw)))
    except Exception:
        return str(uuid.uuid4())

def stable_uuid_for(url: Optional[str], title: Optional[str], content: str) -> str:
    basis = f"{url or ''}|{title or ''}|{content}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, basis))

__all__ = [
    "EMBED_BACKEND", "BACKEND", "EMBED_DIM",
    "QDRANT_COLLECTION", "CHAT_MODEL", "chat_client",
    "embed_batch", "ensure_collection", "qdrant",
    "normalize_point_id", "stable_uuid_for",
]