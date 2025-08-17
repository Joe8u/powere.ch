from pydantic import BaseModel
from .common import TableResponse

# Falls du später stärker typisieren willst, kannst du hier
# konkrete Row-Modelle ergänzen (DemographicsRow etc.)
class DemographicsResponse(TableResponse):
    pass

class Q10IncentiveResponse(TableResponse):
    pass