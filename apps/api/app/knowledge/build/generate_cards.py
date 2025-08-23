# apps/api/app/knowledge/build/generate_cards.py
from __future__ import annotations
from pathlib import Path
import sys, json, re, math
from typing import Dict, Any, List
import yaml

HERE = Path(__file__).resolve()
KNOWLEDGE_DIR = HERE.parents[1]               # .../app/knowledge
CARDS_DIR = KNOWLEDGE_DIR / "cards"
OUT_DIR = KNOWLEDGE_DIR / "build" / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 2500
CHUNK_OVERLAP = 200

def _load_yaml(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _read_text(p: Path) -> str:
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _repo_root() -> Path:
    # .../apps/api/app/knowledge -> repo root is parents[3]
    return KNOWLEDGE_DIR.parents[3]

def _is_code_ref(x: str) -> bool:
    return isinstance(x, str) and x.startswith("code:")

def _resolve_code_ref(ref: str) -> tuple[Path, str]:
    """
    code:steps/stepXX/dir/file.py#module
    Returns (absolute_path, selector)
    """
    assert ref.startswith("code:")
    payload = ref.split("code:", 1)[1]
    if "#" in payload:
        path_part, selector = payload.split("#", 1)
    else:
        path_part, selector = payload, "module"
    path_abs = (_repo_root() / path_part).resolve()
    return path_abs, selector

def _chunk_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == n:
            break
        start = max(end - overlap, start + 1)
    return chunks

def _expand_toc(toc_path: Path, seen: set[str]) -> List[Dict[str, Any]]:
    """
    Produziert eine Liste „Cards“ im Flat-Format:
    { card_id, title, lang, doc_type, source, text }
    Jede code:-Child wird als eigener „Card“-Eintrag erzeugt.
    """
    data = _load_yaml(toc_path)
    if not data or data.get("doc_type") != "toc":
        return []

    base_id = data.get("id") or toc_path.stem
    title = data.get("title") or base_id
    lang = data.get("lang") or "de"
    cards: List[Dict[str, Any]] = []

    children = data.get("children") or []
    for child in children:
        if isinstance(child, str) and _is_code_ref(child):
            code_path, selector = _resolve_code_ref(child)
            text = _read_text(code_path) if code_path.exists() else ""
            card_id = f"{base_id}:{code_path.name}"
            if card_id in seen:
                continue
            seen.add(card_id)
            cards.append({
                "card_id": card_id,
                "title": f"{title} · {code_path.name}",
                "lang": lang,
                "doc_type": "code",
                "source": str(code_path.relative_to(_repo_root())),
                "selector": selector,
                "text": text,
            })
        elif isinstance(child, str) and child.endswith(".yml"):
            # verschachtelte TOC/Doc
            sub_path = (toc_path.parent / child) if not child.startswith("steps/") else (CARDS_DIR / child)
            sub_path = sub_path.resolve()
            if sub_path.exists():
                sub = _load_yaml(sub_path)
                if sub.get("doc_type") == "toc":
                    cards.extend(_expand_toc(sub_path, seen))
                else:
                    # „doc“-Karten ohne code: – packe den beschreibenden Text, falls vorhanden
                    card_id = sub.get("id") or sub_path.stem
                    if card_id in seen:
                        continue
                    seen.add(card_id)
                    text = sub.get("body") or sub.get("description") or ""
                    cards.append({
                        "card_id": card_id,
                        "title": sub.get("title") or card_id,
                        "lang": sub.get("lang") or "de",
                        "doc_type": sub.get("doc_type") or "doc",
                        "source": str(sub_path.relative_to(_repo_root())),
                        "selector": "",
                        "text": text,
                    })
            else:
                # ignorieren (build_toc.py meldet das bereits)
                pass
        else:
            # Roher Verweis (ID o.ä.) -> hier nicht expandiert
            pass
    return cards

def main() -> int:
    if not CARDS_DIR.exists():
        print(f"[ERROR] cards dir not found: {CARDS_DIR}", file=sys.stderr)
        return 1

    # Top-level TOCs (alles unter steps/*/toc.yml)
    toc_paths = sorted((CARDS_DIR / "steps").glob("**/toc.yml"))
    seen: set[str] = set()
    flat_cards: List[Dict[str, Any]] = []
    for p in toc_paths:
        flat_cards.extend(_expand_toc(p, seen))

    if not flat_cards:
        print("[WARN] no cards produced")
    else:
        print(f"[INFO] produced {len(flat_cards)} cards (pre-chunk)")

    # Chunking → JSONL
    out_jsonl = OUT_DIR / "cards.jsonl"
    out_index = OUT_DIR / "cards_index.json"

    total_chunks = 0
    with out_jsonl.open("w", encoding="utf-8") as f:
        for c in flat_cards:
            chunks = _chunk_text(c.get("text", ""))
            for i, ch in enumerate(chunks):
                rec = {
                    "id": f"{c['card_id']}::chunk{ i:04d }",
                    "card_id": c["card_id"],
                    "title": c["title"],
                    "lang": c["lang"],
                    "doc_type": c["doc_type"],
                    "source": c["source"],
                    "selector": c.get("selector", ""),
                    "chunk_index": i,
                    "text": ch,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                total_chunks += 1

    with out_index.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "cards": [
                    {k: v for k, v in c.items() if k != "text"}
                    for c in flat_cards
                ],
                "chunks_file": str(out_jsonl),
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"[OK] wrote {total_chunks} chunks → {out_jsonl}")
    print(f"[OK] wrote card index → {out_index}")
    return 0

if __name__ == "__main__":
    sys.exit(main())