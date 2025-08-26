from fastapi import APIRouter
from app.schemas.common import Message

router = APIRouter()

@router.get("/health", response_model=Message)
@router.get("/healthz", response_model=Message)  # kompatibel zu Docker-Healthcheck
def health():
    return {"message": "ok"}
