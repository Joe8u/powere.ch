from datetime import datetime
from typing import List
from pydantic import BaseModel
from .common import TimeSeriesRow

class LastprofileResponse(BaseModel):
    start: datetime
    end: datetime
    columns: List[str]
    rows: List[TimeSeriesRow]

class AppliancesResponse(BaseModel):
    year: int
    group: bool
    items: List[str]