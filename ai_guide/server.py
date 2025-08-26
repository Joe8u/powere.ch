from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
import json, yaml, pathlib

APP_ROOT = pathlib.Path(__file__).resolve().parent
MANIFESTS = APP_ROOT / "manifests"
KB = APP_ROOT / "kb"
CONFIG = APP_ROOT / "config"

app = FastAPI(title="ai_guide API", version="0.1.0")

def load_json(p): return json.loads(p.read_text(encoding="utf-8"))
def load_yaml(p): return yaml.safe_load(p.read_text(encoding="utf-8"))

@app.get("/config", response_model=dict)
def get_config():
    p = CONFIG / "policy.yaml"
    return load_yaml(p)

@app.get("/steps", response_model=list)
def list_steps():
    p = MANIFESTS / "steps_manifest.json"
    return load_json(p)

@app.get("/steps/{step_id}", response_model=dict)
def get_step(step_id: str):
    steps = load_json(MANIFESTS / "steps_manifest.json")
    for s in steps:
        if s["id"] == step_id:
            return s
    raise HTTPException(404, f"step '{step_id}' not found")

@app.get("/datasets", response_model=dict)
def datasets():
    p = KB / "data_catalog.yaml"
    return load_yaml(p)

@app.get("/kb/overview", response_class=PlainTextResponse)
def kb_overview():
    p = KB / "steps_overview.md"
    return p.read_text(encoding="utf-8")

@app.get("/kb/step/{name}", response_class=PlainTextResponse)
def kb_step(name: str):
    p = KB / "steps" / f"{name}.md"
    if not p.exists():
        raise HTTPException(404, f"{p.name} not found")
    return p.read_text(encoding="utf-8")

@app.get("/kb/search", response_model=list)
def kb_search(q: str):
    """Supersimple Volltextsuche (Dateiname + Inhalt)."""
    hits = []
    for p in KB.rglob("*.md"):
        txt = p.read_text(encoding="utf-8")
        if q.lower() in txt.lower() or q.lower() in p.name.lower():
            hits.append({"path": str(p.relative_to(APP_ROOT)), "title": p.stem})
    return hits
