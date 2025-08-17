from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

class TableResponse(BaseModel):
    total: int
    limit: int
    offset: int
    data: List[Dict[str, Any]]

class Message(BaseModel):
    message: str

class TimeSeriesRow(BaseModel):
    timestamp: datetime
    values: Dict[str, Optional[float]]