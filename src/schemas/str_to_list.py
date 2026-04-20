from pydantic import BaseModel, Field
from typing import List

class StrToListRequest(BaseModel):
    """listrequest parameters"""
    obj: str = Field(..., description='object')

class StrToListResponse(BaseModel):
    """listresponse parameters"""
    infos: List[str] = Field(..., description='stringlist')