from fastapi import APIRouter
from app.schemas.survey import DemographicsResponse, Q10IncentiveResponse
from powere.dataloaders.survey import join_demographics, q10_incentive_wide

router = APIRouter(prefix="/v1/survey", tags=["survey"])

@router.get("/demographics", response_model=DemographicsResponse)
def demographics():
    df = join_demographics()
    return {"rows": df.to_dict(orient="records")}

@router.get("/q10", response_model=Q10IncentiveResponse)
def q10():
    df = q10_incentive_wide()
    return {"rows": df.to_dict(orient="records")}
