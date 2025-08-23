# apps/api/app/knowledge/build/ingest.py
from __future__ import annotations

from pathlib import Path
import os, sys, json
from typing import Iterable, Dict, Any, List
from uuid import UUID, uuid5, NAMESPACE_URL

from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance, Batch
from openai import OpenAI

HERE = Path(__file__).resolve()
KNOWLEDGE_DIR = HERE.parents[1]
OUT_DIR = KNOWLEDGE_DIR / "build" / "out"
JSONL_PATH = OUT_DIR / "cards.jsonl"

# ENV + Defaults
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # optional
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "powere_cards")
# Akzeptiere EMBED_MODEL (neu) oder EMBEDDING_MODEL (alt)
EMBED_MODEL = os.getenv("EMBED_MODEL") or os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"


def _iter_jsonl(p: Path) -> Iterable[Dict[str, Any]]:
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _embed_texts(client: OpenAI, texts: List[str], model: str) -> List[List[float]]:
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def _ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    cols = client.get_collections().collections
    exists = any(c.name == name for c in cols)
    if not exists:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def _make_point_id(raw: str) -> str:
    """
    Qdrant Point-ID muss unsigned int oder UUID sein.
    - Wenn `raw` schon eine UUID ist -> normalisiert zurückgeben
    - sonst deterministische UUIDv5 aus dem String bilden
    """
    try:
        return str(UUID(raw))
    except Exception:
        return str(uuid5(NAMESPACE_URL, raw))


def main() -> int:
    if not JSONL_PATH.exists():
        print(f"[ERROR] chunks file not found: {JSONL_PATH}", file=sys.stderr)
        return 1

    # Clients
    oai = OpenAI()
    qdr = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, prefer_grpc=False)

    # Dimension via Probe bestimmen
    probe_vec = _embed_texts(oai, ["probe"], EMBED_MODEL)[0]
    dim = len(probe_vec)
    _ensure_collection(qdr, QDRANT_COLLECTION, dim)

    BATCH = 64
    buf_ids: List[str] = []
    buf_vecs: List[List[float]] = []
    buf_payloads: List[Dict[str, Any]] = []

    def _flush() -> None:
        if not buf_ids:
            return
        # Typsicher: Batch statt List[PointStruct]
        points = Batch(
            ids=list(buf_ids),
            vectors=list(buf_vecs),
            payloads=list(buf_payloads),
        )
        qdr.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points,
            wait=True,
        )
        buf_ids.clear()
        buf_vecs.clear()
        buf_payloads.clear()

    total = 0
    texts_batch: List[str] = []
    records_batch: List[Dict[str, Any]] = []

    for rec in _iter_jsonl(JSONL_PATH):
        text = rec.get("text", "")
        if not text.strip():
            continue
        texts_batch.append(text)
        records_batch.append(rec)
        if len(texts_batch) >= BATCH:
            vecs = _embed_texts(oai, texts_batch, EMBED_MODEL)
            for r, v in zip(records_batch, vecs):
                rid = str(r.get("id", ""))  # Original-ID im Payload behalten
                buf_ids.append(_make_point_id(rid))  # aber als UUID upserten
                buf_vecs.append(v)
                payload = {k: r[k] for k in r.keys() if k != "text"}
                buf_payloads.append(payload)
            _flush()
            total += len(texts_batch)
            texts_batch.clear()
            records_batch.clear()

    if texts_batch:
        vecs = _embed_texts(oai, texts_batch, EMBED_MODEL)
        for r, v in zip(records_batch, vecs):
            rid = str(r.get("id", ""))
            buf_ids.append(_make_point_id(rid))
            buf_vecs.append(v)
            payload = {k: r[k] for k in r.keys() if k != "text"}
            buf_payloads.append(payload)
        _flush()
        total += len(texts_batch)

    print(f"[OK] ingested {total} chunks into Qdrant collection '{QDRANT_COLLECTION}' (dim={dim})")
    return 0


if __name__ == "__main__":
    sys.exit(main())