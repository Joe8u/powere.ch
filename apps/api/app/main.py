from fastapi import FastAPI
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="powere.ch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.powere.ch", "https://powere.ch", "http://localhost:4321"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestDoc(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    content: str

@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.get("/v1/ping")
def ping():
    return {"msg": "pong"}

@app.post("/v1/ingest")
def ingest(docs: List[IngestDoc] = Body(..., min_items=1)):
    return {"received": len(docs)}