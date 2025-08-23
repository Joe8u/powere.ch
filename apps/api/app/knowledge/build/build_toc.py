# apps/api/app/knowledge/build/build_toc.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Tuple
import sys
import yaml

HERE = Path(__file__).resolve()
# FIX: knowledge/ statt knowledge/build/
KNOWLEDGE_DIR = HERE.parents[1]           # /app/app/knowledge
CARDS_DIR = KNOWLEDGE_DIR / "cards"       # /app/app/knowledge/cards
REPO_ROOT = HERE.parents[3]               # /app

SCHEMES = ("code:", "doc:", "toc:", "explainer:", "artifact:")

def _find_toc_files() -> List[Path]:
    return sorted(CARDS_DIR.glob("**/toc.yml"))

def _split_scheme(s: str) -> Tuple[str, str]:
    for scheme in SCHEMES:
        if s.startswith(scheme):
            return scheme[:-1], s[len(scheme):]
    return "", s

def _resolve_ref(scheme: str, target: str, *, base_dir: Path) -> Path:
    """code: -> REPO_ROOT; alle anderen -> CARDS_DIR"""
    path_part = target.split("#", 1)[0].lstrip("/")
    if scheme == "code":
        return (REPO_ROOT / path_part).resolve()
    return (CARDS_DIR / path_part).resolve()

def _load_yaml(p: Path) -> Dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def main() -> int:
    tocs = _find_toc_files()
    print(f"[INFO] found {len(tocs)} toc.yml files\n")

    missing_total = 0
    for toc_path in tocs:
        toc = _load_yaml(toc_path)
        toc_id = toc.get("id") or str(toc_path.relative_to(CARDS_DIR).with_suffix(""))
        title = toc.get("title", toc_id)
        doc_type = toc.get("doc_type", "toc")

        print(f"┌─ TOC: {toc_path.relative_to(CARDS_DIR)}")
        print(f"│  id='{toc_id}', doc_type='{doc_type}', title='{title}'")

        children = toc.get("children") or []
        for child in children:
            if not isinstance(child, str):
                print(f"│   • [WARN] skip non-string child: {child!r}")
                continue

            scheme, target = _split_scheme(child)
            if scheme in ("doc", "explainer", "artifact"):
                p = _resolve_ref(scheme, target, base_dir=toc_path.parent)
                if p.suffix in (".yml", ".yaml") and not p.exists():
                    print(f"│   • {child}  -> MISSING : {p}")
                    missing_total += 1
                else:
                    print(f"│   • {child}  (assumed card-id or external)")
                continue

            if scheme in ("toc", "code"):
                p = _resolve_ref(scheme, target, base_dir=toc_path.parent)
                if not p.exists():
                    print(f"│   • {child}  -> MISSING : {p}")
                    missing_total += 1
                else:
                    print(f"│   • {child}  -> OK")
                continue

            print(f"│   • {child}  (unknown or freeform)")

        print("└")

    if missing_total:
        print(f"\n[WARN] {missing_total} missing references detected.")
        return 1

    print("\n[OK] All TOCs resolved.")
    return 0

if __name__ == "__main__":
    sys.exit(main())