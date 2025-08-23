# apps/api/app/knowledge/build/build_toc.py
from __future__ import annotations
from pathlib import Path
import sys
import yaml

HERE = Path(__file__).resolve()
KNOWLEDGE_DIR = HERE.parents[1]            # .../app/knowledge
CARDS_DIR = KNOWLEDGE_DIR / "cards"        # .../app/knowledge/cards

def _load_yaml(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _is_code_ref(x: str) -> bool:
    return isinstance(x, str) and x.startswith("code:")

def _code_target(x: str) -> Path:
    # Format: code:steps/stepXX/path/to/file.py#module
    target = x.split("code:", 1)[1]
    file_part = target.split("#", 1)[0]
    # pfad ist relativ zum Repo-Root; wir leiten Root von knowledge/ ab
    repo_root = KNOWLEDGE_DIR.parents[2]   # .../apps/api/app -> .../(repo root)
    return (repo_root / file_part).resolve()

def main() -> int:
    if not CARDS_DIR.exists():
        print(f"[ERROR] cards dir not found: {CARDS_DIR}", file=sys.stderr)
        return 1

    tocs = sorted(CARDS_DIR.glob("**/toc.yml"))
    if not tocs:
        print("[WARN] no toc.yml files found")
        return 0

    print(f"[INFO] found {len(tocs)} toc.yml files\n")
    errs = 0

    for toc in tocs:
        data = _load_yaml(toc)
        id_ = data.get("id")
        doc_type = data.get("doc_type")
        title = data.get("title")
        children = data.get("children") or []

        print(f"┌─ TOC: {toc.relative_to(CARDS_DIR)}")
        print(f"│  id={id_!r}, doc_type={doc_type!r}, title={title!r}")
        if doc_type != "toc":
            print("│  [WARN] doc_type != 'toc'")
        if not children:
            print("│  [WARN] no children")
        else:
            for ch in children:
                if isinstance(ch, str):
                    if _is_code_ref(ch):
                        target = _code_target(ch)
                        ok = target.exists()
                        print(f"│   • {ch}  -> {'OK' if ok else 'MISSING'} : {target}")
                        if not ok:
                            errs += 1
                    else:
                        # wir erlauben sowohl weitere YAML-Pfade als auch Card-IDs
                        if ch.endswith(".yml"):
                            yml = (toc.parent / ch).resolve() if not ch.startswith("steps/") else (CARDS_DIR / ch)
                            ok = yml.exists()
                            print(f"│   • {ch}  -> {'OK' if ok else 'MISSING'} : {yml}")
                            if not ok:
                                errs += 1
                        else:
                            print(f"│   • {ch}  (assumed card-id or external)")
                else:
                    print(f"│   • [UNSUPPORTED CHILD TYPE] {ch!r}")
        print("└")

    if errs:
        print(f"\n[FAIL] {errs} missing references detected.", file=sys.stderr)
        return 2
    print("\n[OK] TOCs look good.")
    return 0

if __name__ == "__main__":
    sys.exit(main())