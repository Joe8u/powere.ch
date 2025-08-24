from __future__ import annotations

import os, time, uuid, logging, threading
from typing import Any, List, Optional, Union, Deque, Dict, Literal, cast
from collections import deque
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel
from qdrant_client.http.models import Batch
from openai.types.chat import ChatCompletionMessageParam

import json
from fastapi.responses import StreamingResponse

from ..core import (
    embed_batch, ensure_collection, qdrant,
    normalize_point_id, stable_uuid_for,
    QDRANT_COLLECTION, chat_client, CHAT_MODEL, EMBED_BACKEND,
)

router = APIRouter()
log = logging.getLogger(__name__)

# ----------------- Konversation-Store (in-memory) -----------------
CHAT_TTL_MIN = int(os.getenv("CHAT_TTL_MINUTES", "120"))           # Auto-Prune nach x Minuten Inaktivität
CHAT_MAX_TURNS_STORED = int(os.getenv("CHAT_MAX_TURNS", "10"))     # Max. Runden im Speicher (user+assistant = 2 msgs/Runde)
HISTORY_SEND_TURNS = int(os.getenv("CHAT_HISTORY_SEND_TURNS", "3"))# Wie viele Runden an das LLM mitsenden
MAX_CONTEXT_CHARS = int(os.getenv("CHAT_MAX_CONTEXT_CHARS", "1600"))

_lock = threading.Lock()
_CONV: Dict[str, Deque["ChatMessage"]] = {}
_LAST_SEEN: Dict[str, float] = {}

def _now() -> float:
    return time.time()

def _prune_old():
    cutoff = _now() - CHAT_TTL_MIN * 60
    stale = [cid for cid, ts in _LAST_SEEN.items() if ts < cutoff]
    for cid in stale:
        _CONV.pop(cid, None)
        _LAST_SEEN.pop(cid, None)

# ----------------- Schemas -----------------
class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    question: str
    top_k: int = 5
    conversation_id: Optional[str] = None
    reset: bool = False

# ----------------- Ingest -----------------
@router.post("/v1/ingest")
def ingest(docs: List[IngestDoc] = Body(..., min_items=1)):
    ensure_collection()
    try:
        vectors = embed_batch([d.content for d in docs])
    except Exception as e:
        log.exception("embedding_failed")
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
        log.exception("qdrant_upsert_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_upsert_failed: {e}")

    return {"received": len(docs), "collection": QDRANT_COLLECTION}

# ----------------- Search -----------------
@router.get("/v1/search")
def search(q: str = Query(..., min_length=2), top_k: int = 5) -> dict[str, Any]:
    try:
        query_vec = embed_batch([q])[0]
    except Exception as e:
        log.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")

    try:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        log.exception("qdrant_search_failed")
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

# ----------------- Chat (RAG + Conversation) -----------------
@router.post("/v1/chat")
def chat(req: ChatRequest, debug: bool = Query(False)):
    if not chat_client:
        raise HTTPException(status_code=500, detail="chat_backend_not_configured: set OPENAI_API_KEY")

    # Konversation vorbereiten
    _prune_old()
    with _lock:
        if req.reset and req.conversation_id:
            _CONV.pop(req.conversation_id, None)
            _LAST_SEEN.pop(req.conversation_id, None)

        conv_id = req.conversation_id or str(uuid.uuid4())
        if conv_id not in _CONV:
            _CONV[conv_id] = deque(maxlen=CHAT_MAX_TURNS_STORED * 2)  # 2 Nachrichten pro Runde
        history = _CONV[conv_id]
        _LAST_SEEN[conv_id] = _now()

    t0 = time.perf_counter()
    # 1) Embedding der aktuellen Frage
    try:
        query_vec = embed_batch([req.question])[0]
    except Exception as e:
        log.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")
    t1 = time.perf_counter()

    # 2) Retrieval
    try:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            limit=req.top_k,
            with_payload=True,
        )
    except Exception as e:
        log.exception("qdrant_search_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_search_failed: {e}")
    t2 = time.perf_counter()

    contexts: list[str] = []
    citations: list[dict[str, Any]] = []
    retrieval_meta: list[dict[str, Any]] = []
    for i, h in enumerate(hits, start=1):
        payload = h.payload or {}
        title = payload.get("title") or f"Doc {i}"
        url = payload.get("url")
        content = (payload.get("content") or "")[:MAX_CONTEXT_CHARS]
        contexts.append(f"[{i}] {title}\n{content}")
        citations.append({"id": str(h.id), "title": title, "url": url, "score": h.score})
        retrieval_meta.append({
            "rank": i,
            "id": str(h.id),
            "title": title,
            "url": url,
            "score": h.score,
            "snippet": content[:160],
        })

    # 3) Prompt-Aufbau inkl. kurzer History
    sys_msg = (
        "Du bist der AI-Guide von powere.ch. Beantworte Fragen NUR mit Hilfe des Kontexts. "
        "Wenn der Kontext etwas nicht enthält, sage ehrlich, dass du es nicht weißt. "
        "Antworte knapp und füge Quellenhinweise wie [1], [2] ein, wenn relevant."
    )

    # Letzte N Runden (user/assistant) in die Messages einfügen
    history_to_send: List[ChatCompletionMessageParam] = []
    if HISTORY_SEND_TURNS > 0 and len(history) > 0:
        for msg in list(history)[-2 * HISTORY_SEND_TURNS:]:
            history_to_send.append(
                cast(ChatCompletionMessageParam, {"role": msg.role, "content": msg.content})
            )

    user_msg_content = (
        f"Frage: {req.question}\n\nKontext:\n" + "\n\n".join(contexts)
        if contexts else f"Frage: {req.question}\n\nKontext: (leer)"
    )

    # 4) LLM-Aufruf
    try:
        sys_msg_param  = cast(ChatCompletionMessageParam, {"role": "system", "content": sys_msg})
        user_msg_param = cast(ChatCompletionMessageParam, {"role": "user",   "content": user_msg_content})

        messages: List[ChatCompletionMessageParam] = [sys_msg_param, *history_to_send, user_msg_param]
        completion = chat_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.2,
        )
        answer = (completion.choices[0].message.content or "").strip()
    except Exception as e:
        log.exception("chat_failed")
        raise HTTPException(status_code=502, detail=f"chat_failed: {e}")
    t3 = time.perf_counter()

    # 5) Konversation speichern (User + Assistant)
    with _lock:
        history.append(ChatMessage(role="user", content=req.question))
        history.append(ChatMessage(role="assistant", content=answer))
        _LAST_SEEN[conv_id] = _now()

    # 6) Token-Nutzung robust ermitteln
    token_usage = None
    try:
        u = getattr(completion, "usage", None)
        if u:
            token_usage = {
                "prompt_tokens": getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", None),
                "completion_tokens": getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", None),
                "total_tokens": getattr(u, "total_tokens", None),
            }
    except Exception:
        token_usage = None

    resp: dict[str, Any] = {
        "answer": answer,
        "citations": citations,
        "used_model": CHAT_MODEL,
        "conversation_id": conv_id,
    }

    if debug:
        resp["meta"] = {
            "top_k": req.top_k,
            "timing_ms": {
                "embedding": int((t1 - t0) * 1000),
                "search":    int((t2 - t1) * 1000),
                "llm":       int((t3 - t2) * 1000),
                "total":     int((t3 - t0) * 1000),
            },
            "retrieval": retrieval_meta,
            "backend": {
                "collection": QDRANT_COLLECTION,
                "embed_backend": EMBED_BACKEND,
                "chat_model": CHAT_MODEL,
            },
            "token_usage": token_usage,
            "messages_preview": {
                "history_sent": [m["role"] for m in history_to_send],
                "user": user_msg_content[:240],
            },
        }

    return resp

# --- neu ---
@router.post("/v1/chat/stream")
def chat_stream(req: ChatRequest, debug: bool = Query(False)):
    """
    Server-Sent Events (SSE): streamt die Antwort tokenweise.
    Events:
      - event: meta   -> Vorab-Metadaten (retrieval, citations, conv_id)
      - event: token  -> Delta-Text (kleine Stücke)
      - event: done   -> Abschluss (Timings, usage etc.)
    """
    if not chat_client:
        raise HTTPException(status_code=500, detail="chat_backend_not_configured: set OPENAI_API_KEY")

    def sse(event: str, data: dict) -> bytes:
        # UTF-8, keine ASCII-Escapes; "data:"-Zeilen pro SSE Standard
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")

    # Konversation vorbereiten (wie in /v1/chat)
    _prune_old()
    with _lock:
        conv_id = req.conversation_id or str(uuid.uuid4())
        if conv_id not in _CONV:
            _CONV[conv_id] = deque(maxlen=CHAT_MAX_TURNS_STORED * 2)
        history = _CONV[conv_id]
        _LAST_SEEN[conv_id] = _now()

    t0 = time.perf_counter()
    # 1) Embedding
    try:
        query_vec = embed_batch([req.question])[0]
    except Exception as e:
        log.exception("embedding_failed")
        raise HTTPException(status_code=502, detail=f"embedding_failed: {e}")
    t1 = time.perf_counter()

    # 2) Retrieval
    try:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            limit=req.top_k,
            with_payload=True,
        )
    except Exception as e:
        log.exception("qdrant_search_failed")
        raise HTTPException(status_code=500, detail=f"qdrant_search_failed: {e}")
    t2 = time.perf_counter()

    # Kontexte/Citations/Meta bauen
    contexts: list[str] = []
    citations: list[dict[str, Any]] = []
    retrieval_meta: list[dict[str, Any]] = []
    for i, h in enumerate(hits, start=1):
        payload = h.payload or {}
        title = payload.get("title") or f"Doc {i}"
        url = payload.get("url")
        content = (payload.get("content") or "")[:MAX_CONTEXT_CHARS]
        contexts.append(f"[{i}] {title}\n{content}")
        citations.append({"id": str(h.id), "title": title, "url": url, "score": h.score})
        retrieval_meta.append({
            "rank": i, "id": str(h.id), "title": title, "url": url,
            "score": h.score, "snippet": content[:160],
        })

    sys_msg = (
        "Du bist der AI-Guide von powere.ch. Beantworte Fragen NUR mit Hilfe des Kontexts. "
        "Wenn der Kontext etwas nicht enthält, sage ehrlich, dass du es nicht weißt. "
        "Antworte knapp und füge Quellenhinweise wie [1], [2] ein, wenn relevant."
    )
    history_to_send: List[ChatCompletionMessageParam] = []
    if HISTORY_SEND_TURNS > 0 and len(history) > 0:
        for msg in list(history)[-2*HISTORY_SEND_TURNS:]:
            history_to_send.append(
                cast(ChatCompletionMessageParam, {"role": msg.role, "content": msg.content})
            )

    user_msg_content = (
        f"Frage: {req.question}\n\nKontext:\n" + "\n\n".join(contexts)
        if contexts else f"Frage: {req.question}\n\nKontext: (leer)"
    )

    def gen():
        # 2a) Vorab-Event 'meta' direkt nach Retrieval senden
        pre_meta = {
            "top_k": req.top_k,
            "timing_ms": {
                "embedding": int((t1 - t0) * 1000),
                "search":    int((t2 - t1) * 1000),
                "llm":       None,
                "total":     None,
            },
            "retrieval": retrieval_meta,
            "backend": {
                "collection": QDRANT_COLLECTION,
                "embed_backend": EMBED_BACKEND,
                "chat_model": CHAT_MODEL,
            },
            "token_usage": None,
            "messages_preview": {
                "history_sent": [m["role"] for m in history_to_send],
                "user": user_msg_content[:240],
            },
        }
        yield sse("meta", {
            "conversation_id": conv_id,
            "citations": citations,
            "meta": pre_meta,
        })

        # 3) Stream von OpenAI weiterreichen
    t_llm_start = time.perf_counter()
    answer_buf: list[str] = []
    try:
        # Pylance-safe: lokal referenzieren und prüfen
        client = chat_client
        if client is None:
            yield sse("token", {"delta": "\n⚠ chat_backend_not_configured"})
            return

        sys_msg_param  = cast(ChatCompletionMessageParam, {"role": "system", "content": sys_msg})
        user_msg_param = cast(ChatCompletionMessageParam, {"role": "user",   "content": user_msg_content})
        messages: List[ChatCompletionMessageParam] = [sys_msg_param, *history_to_send, user_msg_param]

        stream = client.chat.completions.create(
            model=CHAT_MODEL, messages=messages, temperature=0.2, stream=True
        )
        for chunk in stream:
            delta = None
            try:
                # OpenAI-SDK: delta.content kann None sein
                delta = chunk.choices[0].delta.content
            except Exception:
                pass
            if delta:
                answer_buf.append(delta)
                yield sse("token", {"delta": delta})
    except Exception as e:
        log.exception("chat_stream_failed")
        yield sse("token", {"delta": f"\n⚠ chat_failed: {e}"})

        t_llm_end = time.perf_counter()
        answer = "".join(answer_buf).strip()

        # 4) Konversation speichern (User + Assistant)
        try:
            with _lock:
                history.append(ChatMessage(role="user", content=req.question))
                history.append(ChatMessage(role="assistant", content=answer))
                _LAST_SEEN[conv_id] = _now()
        except Exception:
            pass

        # 5) Abschluss-Event
        done_meta = {
            "top_k": req.top_k,
            "timing_ms": {
                "embedding": int((t1 - t0) * 1000),
                "search":    int((t2 - t1) * 1000),
                "llm":       int((t_llm_end - t_llm_start) * 1000),
                "total":     int((t_llm_end - t0) * 1000),
            },
            "retrieval": retrieval_meta,
            "backend": {
                "collection": QDRANT_COLLECTION,
                "embed_backend": EMBED_BACKEND,
                "chat_model": CHAT_MODEL,
            },
            "token_usage": None,  # bei Stream meist nicht verfügbar
            "messages_preview": None,
        }
        yield sse("done", {"meta": done_meta})

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # wichtig hinter Nginx
        "Content-Type": "text/event-stream; charset=utf-8",
        "Connection": "keep-alive",
    }
    return StreamingResponse(gen(), headers=headers)