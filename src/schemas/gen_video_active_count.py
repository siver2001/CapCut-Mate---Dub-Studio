"""Query"""
from pydantic import BaseModel, Field

class GenVideoActiveCountResponse(BaseModel):
    """"""
    count: int = Field(..., description='(pending)(processing)，completed/failed')