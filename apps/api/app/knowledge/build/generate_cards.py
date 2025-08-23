# apps/api/app/knowledge/build/generate_cards.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
import sys, json, yaml

HERE = Path(__file__).resolve()
KNOWLEDGE_DIR = HERE.parent
CARDS_DIR = KNOWLEDGE_DIR / "cards"
OUT_DIR = KNOWLEDGE_DIR / "build" / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH = OUT_DIR / "cards.jsonl"

def _iter_card_yamls() -> List[Path]:
    # All YAML under cards/, excluding toc.yml
    files = []
    for p in CARDS_DIR.glob("**/*.yml"):
        if p.name == "toc.yml":
            continue
        files.append(p)
    for p in CARDS_DIR.glob("**/*.yaml"):
        if p.name == "toc.yaml":
            continue
        files.append(p)
    return sorted(set(files))

def _load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _as_text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, (str, int, float)):
        return str(obj)
    if isinstance(obj, list):
        return "\n".join(_as_text(x) for x in obj)
    if isinstance(obj, dict):
        # Flatten dict deterministically
        parts = []
        for k in sorted(obj.keys()):
            parts.append(f"{k}: {_as_text(obj[k])}")
        return "\n".join(parts)
    return str(obj)

def _build_text(card: Dict[str, Any]) -> str:
    # Try common fields, then fallback to full YAML dump
    fields = []
    for k in ("title", "summary", "description", "body", "notes", "details", "content"):
        if k in card:
            fields.append(_as_text(card[k]))

    # Sometimes content is structured in sections
    for k in ("sections", "items"):
        if k in card:
            fields.append(_as_text(card[k]))

    text = "\n\n".join([t for t in fields if t.strip()])
    if not text.strip():
        text = _as_text(card)
    return text

def main() -> int:
    card_files = _iter_card_yamls()
    total = 0

    with JSONL_PATH.open("w", encoding="utf-8") as out:
        for p in card_files:
            try:
                data = _load_yaml(p)
            except Exception as e:
                print(f"[WARN] skip invalid YAML {p}: {e}")
                continue

            card_id = data.get("id") or str(p.relative_to(CARDS_DIR).with_suffix(""))
            title = data.get("title") or p.stem
            lang = data.get("lang", "de")
            doc_type = data.get("doc_type", "page")

            text = _build_text(data)
            if not text.strip():
                # nothing meaningful to embed; skip quietly
                continue

            rec = {
                "id": card_id,
                "title": title,
                "lang": lang,
                "doc_type": doc_type,
                "text": text,
                # keep file info for debugging
                "src_path": str(p.relative_to(CARDS_DIR)),
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += 1

    print(f"[OK] wrote {total} records -> {JSONL_PATH}")
    if total == 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())