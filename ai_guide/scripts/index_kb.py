import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
KB = ROOT / "kb"

def iter_markdown_files():
    for p in KB.rglob("*.md"):
        yield p

def chunk(text, size=1200, overlap=150):
    i = 0
    n = len(text)
    while i < n:
        yield text[i:i+size]
        i += size - overlap

def main():
    out = []
    for md in iter_markdown_files():
        text = md.read_text(encoding="utf-8")
        for i, ch in enumerate(chunk(text)):
            out.append({
                "source": str(md.relative_to(ROOT)),
                "chunk_id": i,
                "text": ch
            })
    out_path = ROOT / "kb_index.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(out)} chunks to {out_path}")

if __name__ == "__main__":
    main()
