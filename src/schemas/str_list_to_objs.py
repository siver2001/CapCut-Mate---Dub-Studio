from pydantic import BaseModel, Field
from typing import List

class StrListToObjsItem(BaseModel):
    """stringlistobjectlist"""
    output: str = Field(..., description='URL')

class StrListToObjsRequest(BaseModel):
    """stringlistobjectlistrequest parameters"""
    infos: List[str] = Field(..., description='stringlist')

class StrListToObjsResponse(BaseModel):
    """stringlistobjectlistresponse parameters"""
    infos: List[StrListToObjsItem] = Field(..., description='objectlist')