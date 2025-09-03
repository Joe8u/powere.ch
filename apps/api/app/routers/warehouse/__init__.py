#apps/api/app/routers/warehouse/__init__.py
from __future__ import annotations
from fastapi import APIRouter
from . import lastprofile, regelenergie, survey_wide, joined
from .utils import WAREHOUSE_ROOT

router = APIRouter(prefix="/warehouse", tags=["warehouse"])

# Mount feature routers
router.include_router(lastprofile.router)
router.include_router(regelenergie.router)
router.include_router(survey_wide.router)
router.include_router(joined.router)

@router.get("/ping")
def ping() -> dict:
    return {"ok": True, "root": WAREHOUSE_ROOT}

