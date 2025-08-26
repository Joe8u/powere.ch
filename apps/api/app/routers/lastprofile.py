from fastapi import APIRouter
from app.schemas.lastprofile import LastprofileResponse, AppliancesResponse
from powere.dataloaders.lastprofile import load_range, list_appliances
from datetime import datetime

router = APIRouter(prefix="/v1/lastprofile", tags=["lastprofile"])

@router.get("", response_model=LastprofileResponse)
def get_lastprofile(start: datetime, end: datetime, group: bool = False):
    df = load_range(start, end, group=group)
    return {"start": start, "end": end, "group": group, "points": df.reset_index().to_dict(orient="records")}

@router.get("/appliances", response_model=AppliancesResponse)
def get_appliances(year: int = 2024):
    return {"year": year, "appliances": list_appliances(year)}
