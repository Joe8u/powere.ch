#apps/api/app/routers/rag.py
from __future__ import annotations

from typing import Any, List, Optional, Union
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel
import logging

from qdrant_client.http.models import Batch
from ..core import (
    embed_batch, ensure_collection, qdrant,
    normalize_point_id, stable_uuid_for,
    QDRANT_COLLECTION, chat_client, CHAT_MODEL,
)

router = APIRouter()

# -------- Schemas --------
class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str

class ChatRequest(BaseModel):
    question: str
    top_k: int = 5

# -------- Ingest --------
@router.post("/v1/ingest")
def ingest(docs: List[IngestDoc] = Body(..., min_items=1)):
    ensure_collection()
    try:
        vectors = embed_batch([d.content for d in docs])
    except Exception as e:
        logging.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    ids: List[Union[str, int]] = []
    payloads: list[dict[str, Any]] = []

    for d, vec in zip(docs, vectors):
        pid = normalize_point_id(d.id) if d.id is not None else stable_uuid_for(d.url, d.title, d.content)
        ids.append(pid)
        payloads.append({"title": d.title, "url": d.url, "content": d.content})

    try:
        batch = Batch(ids=ids, vectors=vectors, payloads=payloads)
        qdrant.upsert(collection_name=QDRANT_COLLECTION, points=batch, wait=True)
    except Exception as e:
        logging.exception("qdrant_upsert_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_upsert_failed: {e}")

    return {"received": len(docs), "collection": QDRANT_COLLECTION}

# -------- Search --------
@router.get("/v1/search")
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

# -------- Chat (RAG) --------
@router.post("/v1/chat")
def chat(req: ChatRequest):
    if not chat_client:
        raise HTTPException(status_code=500, detail="chat_backend_not_configured: set OPENAI_API_KEY")

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
